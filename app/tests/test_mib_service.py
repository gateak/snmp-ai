import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from app.services.mib_service import MIBService


@pytest.fixture
def sample_mib_content():
    """Sample MIB content for testing"""
    return """
    SAMPLE-MIB DEFINITIONS ::= BEGIN

    IMPORTS
        MODULE-IDENTITY, OBJECT-TYPE, Integer32, enterprises
            FROM SNMPv2-SMI;

    sampleMIB MODULE-IDENTITY
        LAST-UPDATED "202001010000Z"
        ORGANIZATION "Test Organization"
        CONTACT-INFO "test@example.com"
        DESCRIPTION  "Sample MIB for testing"
        ::= { enterprises 9999 }

    -- Sample OID definitions
    sampleOID OBJECT-TYPE
        SYNTAX      Integer32
        MAX-ACCESS  read-only
        STATUS      current
        DESCRIPTION "A sample OID"
        ::= { sampleMIB 1 }

    END
    """


def test_mib_service_init():
    """Test MIB service initialization"""
    # Create a mock MIB builder
    with patch("app.services.mib_service.builder.MibBuilder") as mock_builder:
        # Mock the loadModules method
        mock_builder.return_value.loadModules.return_value = None

        # Create the service
        service = MIBService()

        # Check that the service was initialized
        assert service is not None
        assert service.mib_builder is not None
        assert service.mib_view_controller is not None


def test_get_loaded_mibs():
    """Test getting loaded MIBs"""
    # Create a mock MIB builder
    with patch("app.services.mib_service.builder.MibBuilder") as mock_builder:
        # Mock the loadModules method
        mock_builder.return_value.loadModules.return_value = None

        # Create the service with mocked loaded_mibs
        service = MIBService()
        service.loaded_mibs = {"SNMPv2-MIB", "IF-MIB"}

        # Get loaded MIBs
        mibs = service.get_loaded_mibs()

        # Check that the MIBs were returned
        assert len(mibs) == 2
        assert "SNMPv2-MIB" in mibs
        assert "IF-MIB" in mibs


def test_add_mib_file(sample_mib_content):
    """Test adding a MIB file"""
    # Create a temporary MIB file
    with tempfile.NamedTemporaryFile(suffix=".mib", delete=False) as tmp_file:
        tmp_file.write(sample_mib_content.encode())
        tmp_file_path = tmp_file.name

    try:
        # Create a mock MIB service
        with patch("app.services.mib_service.builder.MibBuilder") as mock_builder:
            # Mock the loadModules method
            mock_builder.return_value.loadModules.return_value = None

            # Create the service
            service = MIBService()

            # Mock the compile_mibs method
            with patch.object(service, "_compile_mibs") as mock_compile:
                # Set up the mock to add the MIB to loaded_mibs
                def side_effect(files):
                    mib_name = os.path.splitext(os.path.basename(files[0]))[0]
                    service.loaded_mibs.add(mib_name)

                mock_compile.side_effect = side_effect

                # Add the MIB file
                result = service.add_mib_file(tmp_file_path)

                # Check that the MIB was added
                assert result is True

                # Check that the compile_mibs method was called
                mock_compile.assert_called_once()
    finally:
        # Clean up the temporary file
        os.unlink(tmp_file_path)
