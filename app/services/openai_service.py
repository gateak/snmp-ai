import json
from typing import Dict, Any, Optional
from openai import OpenAI
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

            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )

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

            # Call the OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
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
                summary="Unable to generate summary.",
                query=original_query
            )
