#!/usr/bin/env python3

import asyncio
import json
from app.services.openai_service import OpenAIService
from app.models.query import SNMPQuery, SNMPTarget, SNMPCredentials, SNMPOperation

async def test_process_query():
    """Test the process_query method of the OpenAIService"""
    openai_service = OpenAIService()

    # Test queries
    test_queries = [
        "Get the system description from router at 192.168.97.14",
        "List all interfaces on the switch at 192.168.97.14 using community string 'public'",
        "Check the uptime of the device with IP 192.168.97.14"
    ]

    for query in test_queries:
        print(f"\nProcessing query: {query}")
        result = await openai_service.process_query(query)

        if result:
            print("✓ Successfully processed query")
            print("SNMP Query Details:")
            print(f"  Target: {result.target.host}:{result.target.port}")
            print(f"  Credentials: v{result.credentials.version}" +
                  (f", Community: {result.credentials.community}" if result.credentials.community else ""))
            print(f"  Operation: {result.operation.command}")
            print(f"  OIDs: {', '.join(result.operation.oids) if result.operation.oids else 'None'}")
            print(f"  MIBs: {', '.join(result.operation.mib_names) if result.operation.mib_names else 'None'}")
        else:
            print("✗ Failed to process query")
            print("  Testing direct conversion instead...")

            # Try to manually convert the OpenAI response to the expected format
            direct_result = await manual_process_query(openai_service, query)
            if direct_result:
                print("✓ Successfully processed query with manual conversion")
                print("SNMP Query Details:")
                print(f"  Target: {direct_result.target.host}:{direct_result.target.port}")
                print(f"  Credentials: v{direct_result.credentials.version}" +
                      (f", Community: {direct_result.credentials.community}" if direct_result.credentials.community else ""))
                print(f"  Operation: {direct_result.operation.command}")
                print(f"  OIDs: {', '.join(direct_result.operation.oids) if direct_result.operation.oids else 'None'}")
                print(f"  MIBs: {', '.join(direct_result.operation.mib_names) if direct_result.operation.mib_names else 'None'}")
            else:
                print("✗ Failed to process query with manual conversion")

async def manual_process_query(openai_service, query):
    """Manually process a query by adapting the OpenAI response to the expected format"""
    try:
        # Create the messages for the OpenAI API
        messages = [
            {"role": "system", "content": openai_service.system_prompt},
            {"role": "user", "content": f"Convert this SNMP query to a JSON structure: '{query}'"}
        ]

        # Call the OpenAI API
        response = openai_service.client.chat.completions.create(
            model=openai_service.model,
            messages=messages,
            temperature=openai_service.temperature,
            max_tokens=openai_service.max_tokens,
            response_format={"type": "json_object"}
        )

        # Extract the JSON response
        response_text = response.choices[0].message.content
        print(f"  OpenAI raw response: {response_text}")

        # Parse the JSON response and adapt it to the expected format
        try:
            raw_data = json.loads(response_text)

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

            print(f"  Adapted data: {json.dumps(adapted_data, indent=2)}")

            # Create an SNMPQuery from the adapted data
            snmp_query = SNMPQuery.model_validate(adapted_data)
            return snmp_query

        except json.JSONDecodeError as e:
            print(f"  Failed to parse OpenAI response as JSON: {e}")
            return None
        except Exception as e:
            print(f"  Failed to validate adapted SNMP query: {e}")
            return None

    except Exception as e:
        print(f"  Error manually processing query with OpenAI: {e}")
        return None

async def test_format_response():
    """Test the format_response method of the OpenAIService"""
    openai_service = OpenAIService()

    # Example SNMP response data
    snmp_response = {
        "1.3.6.1.2.1.1.1.0": "Cisco IOS Software, C2900 Software (C2900-UNIVERSALK9-M), Version 15.2(4)M1",
        "1.3.6.1.2.1.1.5.0": "Router1",
        "1.3.6.1.2.1.1.6.0": "Server Room"
    }

    original_query = "What is the system information of the router?"

    print("\nFormatting SNMP response")
    result = await openai_service.format_response(snmp_response, original_query)

    if result:
        print("✓ Successfully formatted response")
        print("\nOriginal Query:")
        print(result.query)
        print("\nRaw Data:")
        print(json.dumps(result.raw_data, indent=2))
        print("\nSummary:")
        print(result.summary)
    else:
        print("✗ Failed to format response")

async def main():
    """Run all tests"""
    print("Testing OpenAI Service")
    print("=====================")

    print("\n1. Testing process_query method")
    await test_process_query()

    print("\n2. Testing format_response method")
    await test_format_response()

if __name__ == "__main__":
    asyncio.run(main())
