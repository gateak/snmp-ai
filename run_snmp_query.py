#!/usr/bin/env python3

import asyncio
import json
from app.services.openai_service import OpenAIService
from app.services.snmp_service import SNMPService
from app.models.query import SNMPQuery

async def run_query(query_text):
    """Run an SNMP query using the OpenAI service and SNMP service"""
    print(f"Processing query: {query_text}")

    # Initialize services
    openai_service = OpenAIService()
    snmp_service = SNMPService()

    # Process query with OpenAI
    snmp_query = await openai_service.process_query(query_text)

    if not snmp_query:
        print("Error: Failed to generate SNMP query")
        return

    # Print query details
    print("\nGenerated SNMP Query:")
    print(json.dumps(snmp_query.dict(), indent=2))

    # Execute SNMP query
    print(f"\nExecuting SNMP {snmp_query.operation.command} query to {snmp_query.target.host}...")
    result = await snmp_service.execute_query(snmp_query)

    # Print result
    print("\nResult:")
    print(json.dumps(result, indent=2))

    # Format response with OpenAI
    formatted_response = await openai_service.format_response(result, query_text)

    print("\nSummary:")
    print(formatted_response.summary)

if __name__ == "__main__":
    # Test query for 192.168.97.14
    test_query = "Get the system description from the device at 192.168.97.14"

    # Run the query
    asyncio.run(run_query(test_query))
