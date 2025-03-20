#!/usr/bin/env python3
import sys
import argparse
import uvicorn

def main():
    """
    SNMP-AI: AI-powered SNMP query system
    """
    parser = argparse.ArgumentParser(description="SNMP-AI: AI-powered SNMP query system")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # API server command
    api_parser = subparsers.add_parser("api", help="Start the API server")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    api_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # CLI command
    cli_parser = subparsers.add_parser("cli", help="Run CLI commands")
    cli_parser.add_argument("args", nargs=argparse.REMAINDER, help="CLI arguments")

    args = parser.parse_args()

    if args.command == "api":
        # Start FastAPI server
        uvicorn.run(
            "app.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    elif args.command == "cli":
        # Run CLI command
        from app.cli import main as cli_main
        import asyncio

        # Reconstruct sys.argv for the CLI
        sys.argv = [sys.argv[0]] + args.args
        asyncio.run(cli_main())
    else:
        # Print help
        parser.print_help()

if __name__ == "__main__":
    main()
