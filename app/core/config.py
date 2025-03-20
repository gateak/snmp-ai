import os
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SNMPConfig(BaseModel):
    default_community: str = "public"
    default_version: str = "2c"
    default_port: int = 161
    timeout: int = 5
    retries: int = 3


class OpenAIConfig(BaseModel):
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4")
    temperature: float = 0.1
    max_tokens: int = 2000
    system_prompt: str = """
You are a specialized AI assistant for SNMP queries. Your role is to convert natural language
SNMP queries into structured JSON requests that can be processed by an SNMP scanner.

Your response should be a valid JSON object with exactly this structure:
{
  "target": {
    "host": "IP_ADDRESS_OR_HOSTNAME",
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


class AppConfig(BaseModel):
    app_name: str = "SNMP-AI"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    mib_directory: str = os.getenv("MIB_DIRECTORY", "./mibs")
    cache_enabled: bool = True
    cache_ttl: int = 3600  # seconds
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    snmp: SNMPConfig = SNMPConfig()
    openai: OpenAIConfig = OpenAIConfig()


# Create a singleton config instance
config = AppConfig()
