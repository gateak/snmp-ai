import pytest
import os
from unittest.mock import patch, MagicMock

from app.services.openai_service import OpenAIService
from app.models.query import SNMPQuery, SNMPTarget, SNMPOperation, SNMPCredentials


@pytest.mark.asyncio
async def test_process_query():
    """Test processing a natural language query"""
    # Skip test if OpenAI API key is not set
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not set")

    # Sample response from OpenAI
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"target": {"host": "192.168.1.1", "port": 161}, "operation": {"command": "GET", "oids": [".1.3.6.1.2.1.1.1.0"]}}'
            )
        )
    ]

    # Mock the OpenAI client
    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create the service
        service = OpenAIService()

        # Process a query
        query = "Get system description for 192.168.1.1"
        result = await service.process_query(query)

        # Check that the result is valid
        assert result is not None
        assert isinstance(result, SNMPQuery)
        assert result.target.host == "192.168.1.1"
        assert result.operation.command == "GET"
        assert ".1.3.6.1.2.1.1.1.0" in result.operation.oids


@pytest.mark.asyncio
async def test_format_response():
    """Test formatting an SNMP response"""
    # Skip test if OpenAI API key is not set
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key not set")

    # Sample response from OpenAI
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="The system description is: Linux Ubuntu 20.04"
            )
        )
    ]

    # Mock the OpenAI client
    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create the service
        service = OpenAIService()

        # Format a response
        snmp_response = {
            "SNMPv2-MIB::sysDescr.0": "Linux Ubuntu 20.04"
        }
        query = "Get system description for 192.168.1.1"

        result = await service.format_response(snmp_response, query)

        # Check that the result is valid
        assert result is not None
        assert result.raw_data == snmp_response
        assert result.query == query
        assert "Linux Ubuntu 20.04" in result.summary
