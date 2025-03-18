# SNMP-AI: Intelligent SNMP Management System

An intelligent SNMP management system that uses LLMs to interpret natural language queries and execute SNMP operations on network devices.

## Features

- Natural language query interpretation using LLMs
- SNMP operations (GET, WALK, BULKWALK)
- MIB management and caching
- Response caching for improved performance
- Concurrent SNMP operations
- RESTful API interface

## Prerequisites

- Go 1.21 or later (for local development)
- Redis server (included in Docker setup)
- LLM API key (e.g., OpenAI API key)

## Installation

### Using Docker (Recommended)

1. Make sure you have Docker and Docker Compose installed.

2. Set your LLM API key:
   ```bash
   export LLM_API_KEY=your_api_key_here
   ```

3. Build and start the services:
   ```bash
   docker-compose up -d
   ```

4. The API will be available at http://localhost:8080

### Manual Installation

1. Install Go 1.21 or later.

2. Install Redis server and start it:
   ```bash
   redis-server
   ```

3. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://your-repo-url.git
   cd snmp-ai
   ```

4. Install dependencies:
   ```bash
   go mod download
   ```

5. Set up environment variables:
   ```bash
   export LLM_API_KEY=your_api_key_here
   ```

6. Build and run the application:
   ```bash
   go run cmd/server/main.go
   ```

## Configuration

The application can be configured through `configs/config.yaml`. Key configuration options:

- API server settings (host, port)
- SNMP settings (version, community, timeout, retries)
- MIB repository settings
- LLM settings (model, max tokens, temperature)
- Redis connection settings

Environment variables:
- `LLM_API_KEY`: API key for the LLM service
- `REDIS_HOST`: Redis host (defaults to "localhost", or "redis" in Docker)
- `REDIS_PORT`: Redis port (defaults to 6379)

## API Usage

### Natural Language Query

```bash
curl -X POST http://localhost:8080/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me all interfaces on device 192.168.1.1"}'
```

### List Available MIBs

```bash
curl http://localhost:8080/api/v1/mibs
```

### Load MIB

```bash
curl -X POST http://localhost:8080/api/v1/mibs/IF-MIB
```

## Project Structure

```
snmp-ai/
├── cmd/
│   └── server/          # Application entry point
├── internal/
│   ├── api/            # API server implementation
│   ├── snmp/           # SNMP client implementation
│   ├── mib/            # MIB management
│   └── llm/            # LLM integration
├── configs/            # Configuration files
├── docker/            # Docker-related files
├── Dockerfile         # Main application Dockerfile
└── docker-compose.yaml # Docker Compose configuration
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
