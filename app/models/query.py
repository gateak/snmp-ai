from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class SNMPCredentials(BaseModel):
    """SNMP authentication credentials"""
    version: str = Field("2c", description="SNMP version (1, 2c, 3)")
    community: Optional[str] = Field(None, description="Community string for SNMP v1/v2c")

    # SNMPv3 specific fields
    username: Optional[str] = Field(None, description="Username for SNMPv3")
    auth_protocol: Optional[str] = Field(None, description="Authentication protocol for SNMPv3 (MD5, SHA)")
    auth_password: Optional[str] = Field(None, description="Authentication password for SNMPv3")
    priv_protocol: Optional[str] = Field(None, description="Privacy protocol for SNMPv3 (DES, AES)")
    priv_password: Optional[str] = Field(None, description="Privacy password for SNMPv3")


class SNMPTarget(BaseModel):
    """Target information for SNMP query"""
    host: str = Field(..., description="Target IP address or hostname")
    port: int = Field(161, description="SNMP port")
    timeout: int = Field(5, description="Timeout in seconds")
    retries: int = Field(3, description="Number of retries")


class SNMPOperation(BaseModel):
    """SNMP operation details"""
    command: str = Field(..., description="SNMP command (GET, GETNEXT, WALK, BULK, etc.)")
    oids: List[str] = Field([], description="List of OIDs to query")
    mib_names: List[str] = Field([], description="List of MIB names to query")
    max_repetitions: Optional[int] = Field(None, description="Max repetitions for BULK operations")
    non_repeaters: Optional[int] = Field(None, description="Non-repeaters for BULK operations")


class SNMPQuery(BaseModel):
    """Complete SNMP query model"""
    target: SNMPTarget
    credentials: SNMPCredentials = Field(default_factory=SNMPCredentials)
    operation: SNMPOperation
    raw_query: Optional[str] = Field(None, description="Original natural language query")


class SNMPResponse(BaseModel):
    """SNMP response model"""
    raw_data: Dict[str, Any] = Field(..., description="Raw SNMP response data")
    summary: str = Field(..., description="Human-readable summary of the response")
    query: str = Field(..., description="Original natural language query")
    error: Optional[str] = Field(None, description="Error message if the query failed")
