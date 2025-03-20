# SNMP-AI

An AI-powered SNMP query system that translates natural language queries into SNMP commands.

## Overview

SNMP-AI is a Python-based application that utilizes OpenAI's API to facilitate natural language queries for SNMP (Simple Network Management Protocol) data. The application acts as an intermediary, translating human-readable queries into structured JSON requests suitable for a high-performance SNMP scanner.

## Features

- Natural language interface for SNMP queries
- Integration with OpenAI's API for query processing
- Support for SNMP v1, v2c protocols
- MIB processing and OID mapping
- Structured JSON output for responses
- Query caching for improved performance
- RESTful API for integration with other systems
- CLI for command-line usage

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/snmp-ai.git
cd snmp-ai
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file based on the provided example:

```bash
cp .env.example .env
```

4. Edit the `.env` file and add your OpenAI API key:

```
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4  # Or another available model
```

## Usage

### Running the API Server

```bash
python main.py api --host 0.0.0.0 --port 8000
```

Or directly with uvicorn:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

### Using the CLI

Process a query:

```bash
python main.py cli query "Get the system description from the device at 192.168.1.1"
```

List loaded MIBs:

```bash
python main.py cli mibs list
```

Add a MIB file:

```bash
python main.py cli mibs add /path/to/mib/file
```

Resolve an OID:

```bash
python main.py cli oid resolve sysDescr
```

Translate an OID:

```bash
python main.py cli oid translate 1.3.6.1.2.1.1.1.0
```

### Using the Explorer Tool

The SNMP Explorer provides a comprehensive analysis of SNMP devices:

```bash
python snmp_explorer.py 192.168.1.1 --community public --mode standard
```

Available modes:
- `standard`: Basic device analysis
- `executive`: Executive-friendly summary
- `discover`: Detailed device discovery

Save the analysis to a file:

```bash
python snmp_explorer.py 192.168.1.1 -o device-report.json
```

## API Endpoints

- `GET /`: Health check and API information
- `POST /query`: Process a natural language SNMP query
- `GET /mibs`: List loaded MIBs
- `POST /mibs/upload`: Upload a new MIB file
- `POST /oid/resolve`: Resolve an OID name to a numeric OID
- `POST /oid/translate`: Translate a numeric OID to a symbolic name
- `POST /clear-cache`: Clear the application cache
- `GET /cache/stats`: Get cache statistics

## Example Queries

- "What is the system description of the device at 192.168.1.1?"
- "Walk the interfaces table on 10.0.0.1 using community string 'public'"
- "Get the uptime of 172.16.1.10 using SNMP version 2c"
- "Check the CPU usage on the switch at 192.168.10.5"
- "List all interfaces and their status on 10.0.1.1"

## Docker Deployment

Build and run the Docker container:

```bash
docker-compose up -d
```

## License

MIT License
