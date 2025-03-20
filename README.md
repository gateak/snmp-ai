# SNMP-AI

An AI-powered SNMP query system that translates natural language queries into SNMP commands.

## Overview

SNMP-AI is a Python-based application that utilizes OpenAI's API to facilitate natural language queries for SNMP (Simple Network Management Protocol) data. The application acts as an intermediary, translating human-readable queries into structured JSON requests suitable for a high-performance SNMP scanner.

## Features

- Natural language interface for SNMP queries
- Integration with OpenAI's API for query processing
- Support for SNMP v1, v2c, v3
- MIB processing and OID mapping
- Structured JSON output for responses
- Query caching for improved performance

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Or use the API:

```bash
uvicorn api.main:app --reload
```

## Example Queries

- "What MIBs are available on this IP?"
- "List all available network interfaces in this subnet."
- "Fetch SNMP uptime for this device."
