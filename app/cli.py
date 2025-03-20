import asyncio
import argparse
import json
import sys
import os
from typing import Dict, Any, Optional

from loguru import logger

from app.core.config import config
from app.services.openai_service import OpenAIService
from app.services.snmp_service import SNMPService
from app.services.mib_service import MIBService
from app.models.query import SNMPQuery


async def process_query(query: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Process a natural language SNMP query

    Args:
        query: Natural language query
        verbose: Whether to print verbose output

    Returns:
        Query response
    """
    try:
        openai_service = OpenAIService()
        mib_service = MIBService()
        snmp_service = SNMPService(mib_service=mib_service)

        # Process query with OpenAI
        if verbose:
            print(f"Processing query: {query}")

        snmp_query = await openai_service.process_query(query)

        if not snmp_query:
            print("Error: Failed to parse query")
            return {"error": "Failed to parse query"}

        if verbose:
            print("\nGenerated SNMP Query:")
            print(json.dumps(snmp_query.dict(), indent=2))

        # Store original query
        snmp_query.raw_query = query

        # Execute SNMP query
        if verbose:
            print(f"\nExecuting SNMP {snmp_query.operation.command} query to {snmp_query.target.host}...")

        snmp_response_data = await snmp_service.execute_query(snmp_query)

        # Format response
        if "error" in snmp_response_data:
            if verbose:
                print(f"\nError: {snmp_response_data['error']}")
            return {"error": snmp_response_data["error"]}

        # Use OpenAI to generate a summary
        if verbose:
            print("\nGenerating summary...")

        formatted_response = await openai_service.format_response(snmp_response_data, query)

        if verbose:
            print("\nSummary:")
            print(formatted_response.summary)

        return formatted_response.dict()

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return {"error": f"Error processing query: {str(e)}"}


async def list_mibs():
    """List available MIBs"""
    try:
        mib_service = MIBService()
        mibs = mib_service.get_loaded_mibs()

        if mibs:
            print(f"Available MIBs ({len(mibs)}):")
            for mib in sorted(mibs):
                print(f"- {mib}")
        else:
            print("No MIBs available")

    except Exception as e:
        logger.error(f"Error listing MIBs: {e}")
        print(f"Error listing MIBs: {str(e)}")


async def add_mib(file_path: str):
    """Add a new MIB file"""
    try:
        mib_service = MIBService()
        success = mib_service.add_mib_file(file_path)

        if success:
            print(f"MIB file added successfully")
        else:
            print(f"Failed to add MIB file")

    except Exception as e:
        logger.error(f"Error adding MIB: {e}")
        print(f"Error adding MIB: {str(e)}")


async def translate_oid(oid: str):
    """Translate a numeric OID to a symbolic name"""
    try:
        mib_service = MIBService()
        name = mib_service.translate_oid(oid)

        if name:
            print(f"OID: {oid}")
            print(f"Name: {name}")
        else:
            print(f"OID not found: {oid}")

    except Exception as e:
        logger.error(f"Error translating OID: {e}")
        print(f"Error translating OID: {str(e)}")


async def resolve_oid(name: str):
    """Resolve an OID name to a numeric OID"""
    try:
        mib_service = MIBService()
        oid = mib_service.resolve_oid(name)

        if oid:
            print(f"Name: {name}")
            print(f"OID: {oid}")
        else:
            print(f"Name not found: {name}")

    except Exception as e:
        logger.error(f"Error resolving OID: {e}")
        print(f"Error resolving OID: {str(e)}")


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="SNMP-AI: AI-powered SNMP query system")

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Query command
    query_parser = subparsers.add_parser("query", help="Process a natural language SNMP query")
    query_parser.add_argument("query", help="Natural language query")
    query_parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")
    query_parser.add_argument("-o", "--output", help="Output file for results (JSON format)")

    # MIB commands
    mib_parser = subparsers.add_parser("mibs", help="MIB management")
    mib_subparsers = mib_parser.add_subparsers(dest="mib_command", help="MIB command")

    # List MIBs
    mib_list_parser = mib_subparsers.add_parser("list", help="List available MIBs")

    # Add MIB
    mib_add_parser = mib_subparsers.add_parser("add", help="Add a new MIB file")
    mib_add_parser.add_argument("file_path", help="Path to MIB file")

    # OID commands
    oid_parser = subparsers.add_parser("oid", help="OID management")
    oid_subparsers = oid_parser.add_subparsers(dest="oid_command", help="OID command")

    # Translate OID
    oid_translate_parser = oid_subparsers.add_parser("translate", help="Translate a numeric OID to a symbolic name")
    oid_translate_parser.add_argument("oid", help="Numeric OID to translate")

    # Resolve OID
    oid_resolve_parser = oid_subparsers.add_parser("resolve", help="Resolve an OID name to a numeric OID")
    oid_resolve_parser.add_argument("name", help="OID name to resolve")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Process commands
    if args.command == "query":
        result = await process_query(args.query, args.verbose)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
                print(f"Results saved to {args.output}")
        elif not args.verbose:
            # Print summary in non-verbose mode
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(result["summary"])

    elif args.command == "mibs":
        if args.mib_command == "list":
            await list_mibs()
        elif args.mib_command == "add":
            await add_mib(args.file_path)
        else:
            mib_parser.print_help()

    elif args.command == "oid":
        if args.oid_command == "translate":
            await translate_oid(args.oid)
        elif args.oid_command == "resolve":
            await resolve_oid(args.name)
        else:
            oid_parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
