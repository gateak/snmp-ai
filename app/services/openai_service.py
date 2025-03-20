import json
import time
import asyncio
from typing import Dict, Any, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai import APIError, RateLimitError, APIConnectionError, OpenAIError
from loguru import logger

from app.core.config import config
from app.models.query import SNMPQuery, SNMPResponse, SNMPTarget, SNMPCredentials, SNMPOperation

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=config.openai.api_key)
        self.model = config.openai.model
        self.temperature = config.openai.temperature
        self.max_tokens = config.openai.max_tokens
        self.system_prompt = config.openai.system_prompt
        self.max_retries = 3
        self.retry_base_delay = 1  # seconds

    async def process_query(self, query: str) -> Optional[SNMPQuery]:
        """
        Process a natural language query using OpenAI API and convert it to an SNMP query.

        Args:
            query: The natural language query from the user

        Returns:
            SNMPQuery object containing structured SNMP request parameters
        """
        try:
            logger.debug(f"Processing query with OpenAI: {query}")

            # Create the messages for the OpenAI API
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Convert this SNMP query to a JSON structure: '{query}'"}
            ]

            # Call the OpenAI API with retry logic
            response = await self._call_openai_with_retry(
                messages=messages,
                response_format={"type": "json_object"}
            )

            if not response:
                logger.error("Failed to get a response from OpenAI API after retries")
                return None

            # Extract the JSON response
            response_text = response.choices[0].message.content
            logger.debug(f"OpenAI response: {response_text}")

            # Parse the JSON response
            try:
                raw_data = json.loads(response_text)

                # Check if response matches expected format
                if "target" in raw_data and "operation" in raw_data:
                    # Response is already in the expected format
                    snmp_query = SNMPQuery.model_validate(raw_data)
                else:
                    # Adapt the response to match the expected SNMPQuery model
                    adapted_data = {
                        "target": {
                            "host": raw_data.get("target_ip", ""),
                            "port": raw_data.get("port", 161),
                            "timeout": raw_data.get("timeout", 5),
                            "retries": raw_data.get("retries", 3)
                        },
                        "credentials": {
                            "version": raw_data.get("snmp_version", "2c"),
                            "community": raw_data.get("community_string", "public")
                        },
                        "operation": {
                            "command": raw_data.get("operation", "GET"),
                            "oids": [raw_data.get("oid", "1.3.6.1.2.1.1.1.0")]
                        }
                    }
                    logger.debug(f"Adapted data: {json.dumps(adapted_data)}")
                    snmp_query = SNMPQuery.model_validate(adapted_data)

                logger.info(f"Successfully processed query into SNMP request")
                return snmp_query

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response as JSON: {e}")
                return None
            except Exception as e:
                logger.error(f"Failed to validate SNMP query: {e}")
                return None

        except Exception as e:
            logger.error(f"Error processing query with OpenAI: {e}")
            return None

    async def format_response(self, snmp_response: Dict[str, Any], original_query: str) -> SNMPResponse:
        """
        Format the SNMP response into a more user-friendly format using OpenAI.

        Args:
            snmp_response: The raw SNMP response data
            original_query: The original natural language query

        Returns:
            Formatted SNMPResponse object
        """
        try:
            logger.debug(f"Formatting SNMP response with OpenAI")

            # Create the messages for the OpenAI API
            messages = [
                {"role": "system", "content": "You are a helpful assistant that explains SNMP responses in plain language."},
                {"role": "user", "content": f"Original query: '{original_query}'\nSNMP response: {json.dumps(snmp_response)}\n\nProvide a concise summary of this SNMP data."}
            ]

            # Call the OpenAI API with retry logic
            response = await self._call_openai_with_retry(messages=messages)

            if not response:
                logger.error("Failed to get a summary response from OpenAI API after retries")
                return SNMPResponse(
                    raw_data=snmp_response,
                    summary="Unable to generate summary due to API error.",
                    query=original_query
                )

            # Extract the response
            summary = response.choices[0].message.content

            return SNMPResponse(
                raw_data=snmp_response,
                summary=summary,
                query=original_query
            )

        except Exception as e:
            logger.error(f"Error formatting response with OpenAI: {e}")
            return SNMPResponse(
                raw_data=snmp_response,
                summary="Unable to generate summary due to an unexpected error.",
                query=original_query
            )

    async def _call_openai_with_retry(self, messages: list, response_format=None) -> Optional[ChatCompletion]:
        """
        Call OpenAI API with exponential backoff retry logic

        Args:
            messages: The messages to send to the API
            response_format: Optional format specification for the response

        Returns:
            ChatCompletion response object or None if all retries fail
        """
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                # Build kwargs based on whether response_format is provided
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                }

                if response_format:
                    kwargs["response_format"] = response_format

                # Call the OpenAI API - this is synchronous in the new OpenAI Python client
                return self.client.chat.completions.create(**kwargs)

            except RateLimitError as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Rate limit exceeded, max retries reached: {e}")
                    return None

                # Calculate backoff delay with jitter
                delay = self.retry_base_delay * (2 ** (retry_count - 1)) + (time.time() % 1)
                logger.warning(f"Rate limit exceeded, retrying in {delay:.2f} seconds (attempt {retry_count}/{self.max_retries})")
                # Use asyncio.sleep for async waiting
                await asyncio.sleep(delay)

            except APIConnectionError as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"API connection error, max retries reached: {e}")
                    return None

                delay = self.retry_base_delay * retry_count
                logger.warning(f"API connection error, retrying in {delay} seconds (attempt {retry_count}/{self.max_retries})")
                await asyncio.sleep(delay)

            except APIError as e:
                # Only retry on 5xx errors
                if e.status_code and 500 <= e.status_code < 600:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        logger.error(f"Server error {e.status_code}, max retries reached: {e}")
                        return None

                    delay = self.retry_base_delay * retry_count
                    logger.warning(f"Server error {e.status_code}, retrying in {delay} seconds (attempt {retry_count}/{self.max_retries})")
                    await asyncio.sleep(delay)
                else:
                    # Don't retry on 4xx errors
                    logger.error(f"API error: {e}")
                    return None

            except OpenAIError as e:
                # General OpenAI error, don't retry
                logger.error(f"OpenAI API error: {e}")
                return None

            except Exception as e:
                # Unexpected error, don't retry
                logger.error(f"Unexpected error calling OpenAI API: {e}")
                return None

        return None  # All retries failed
