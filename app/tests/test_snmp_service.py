import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from app.services.snmp_service import SNMPService
from app.services.mib_service import MIBService
from app.models.query import SNMPQuery, SNMPTarget, SNMPOperation, SNMPCredentials


@pytest.mark.asyncio
async def test_execute_query():
    """Test executing an SNMP query"""
    # Create a mock MIB service
    mock_mib_service = MagicMock(spec=MIBService)
    mock_mib_service.translate_oid.return_value = "SNMPv2-MIB::sysDescr.0"
    mock_mib_service.resolve_oid.return_value = ".1.3.6.1.2.1.1.1.0"

    # Create mock SNMP results
    async def mock_execute_get(*args, **kwargs):
        return {"SNMPv2-MIB::sysDescr.0": "Linux Ubuntu 20.04"}

    # Patch the execute methods
    with patch.object(SNMPService, '_execute_get', new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = mock_execute_get

        # Create the service
        service = SNMPService(mib_service=mock_mib_service)

        # Create a query
        query = SNMPQuery(
            target=SNMPTarget(host="192.168.1.1", port=161),
            credentials=SNMPCredentials(version="2c", community="public"),
            operation=SNMPOperation(command="GET", oids=[".1.3.6.1.2.1.1.1.0"])
        )

        # Execute the query
        result = await service.execute_query(query)

        # Check that the result is valid
        assert result is not None
        assert "SNMPv2-MIB::sysDescr.0" in result
        assert result["SNMPv2-MIB::sysDescr.0"] == "Linux Ubuntu 20.04"

        # Verify that the method was called
        mock_get.assert_called_once()
