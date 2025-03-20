#!/usr/bin/env python3

import asyncio
from app.core.config import config
from app.services.openai_service import OpenAIService

def update_system_prompt():
    """Update the system prompt in the OpenAIService to produce the expected format"""
    improved_prompt = """
You are a specialized AI assistant for SNMP queries. Your role is to convert natural language
SNMP queries into structured JSON requests that can be processed by an SNMP scanner.

Your response should be a valid JSON object with exactly this structure:
{
  "target": {
    "host": "192.168.97.14",
    "port": 161,
    "timeout": 5,
    "retries": 3
  },
  "credentials": {
    "version": "2c",
    "community": "public"
  },
  "operation": {
    "command": "GET",
    "oids": ["1.3.6.1.2.1.1.1.0"],
    "mib_names": []
  }
}

Where:
- "target.host" is the IP address or hostname from the query (REQUIRED)
- "target.port" is the SNMP port (default: 161)
- "target.timeout" is the timeout in seconds (default: 5)
- "target.retries" is the number of retries (default: 3)
- "credentials.version" is the SNMP version: "1", "2c", or "3" (default: "2c")
- "credentials.community" is the community string for v1/v2c (default: "public")
- "operation.command" is one of: "GET", "GETNEXT", "WALK", "BULK" (REQUIRED)
- "operation.oids" is an array of OID strings (REQUIRED)
- "operation.mib_names" is an array of MIB names (optional)

Don't deviate from this exact structure. Every field must appear exactly as shown.
"""

    # Print the current prompt
    print("Current system prompt:")
    print("=====================")
    print(config.openai.system_prompt)

    # Print the improved prompt
    print("\nImproved system prompt:")
    print("=====================")
    print(improved_prompt)

    # Instructions for updating the prompt
    print("\nTo apply this improved prompt:")
    print("1. Edit the file app/core/config.py")
    print("2. Replace the system_prompt value with the improved prompt")
    print("3. Save the file and restart your application")

if __name__ == "__main__":
    update_system_prompt()
