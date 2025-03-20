import asyncio
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from puresnmp import Client, V1, V2C, ObjectIdentifier
from puresnmp.exc import SnmpError, Timeout

from app.models.query import SNMPQuery, SNMPTarget, SNMPCredentials, SNMPOperation
from app.core.config import config
from app.services.mib_service import MIBService


class SNMPService:
    def __init__(self, mib_service: Optional[MIBService] = None):
        self.mib_service = mib_service or MIBService()

    async def execute_query(self, query: SNMPQuery) -> Dict[str, Any]:
        """
        Execute an SNMP query based on the structured query object

        Args:
            query: Structured SNMP query object

        Returns:
            Dictionary containing the SNMP response data
        """
        try:
            logger.info(f"Executing SNMP {query.operation.command} query to {query.target.host}")

            # Prepare OIDs
            oids = self._prepare_oids(query.operation)
            if not oids:
                return {"error": "No valid OIDs specified"}

            # Get community string for v1/v2c
            community = query.credentials.community or config.snmp.default_community

            # Create SNMP client with proper credentials
            try:
                if query.credentials.version == "1":
                    client = Client(
                        query.target.host,
                        V1(community),
                        port=query.target.port
                    )
                elif query.credentials.version == "2c":
                    client = Client(
                        query.target.host,
                        V2C(community),
                        port=query.target.port
                    )
                else:
                    return {"error": "Only SNMP versions 1 and 2c are currently supported"}
            except Exception as e:
                logger.error(f"Failed to create SNMP client: {str(e)}")
                return {"error": f"Failed to create SNMP client: {str(e)}"}

            # Execute SNMP command
            try:
                if query.operation.command.upper() == "GET":
                    result = await self._execute_get(client, oids)
                elif query.operation.command.upper() == "GETNEXT":
                    result = await self._execute_getnext(client, oids)
                elif query.operation.command.upper() == "WALK":
                    result = await self._execute_walk(client, oids)
                elif query.operation.command.upper() == "BULK":
                    result = await self._execute_bulk(
                        client, oids,
                        non_repeaters=query.operation.non_repeaters or 0,
                        max_repetitions=query.operation.max_repetitions or 10
                    )
                else:
                    return {"error": f"Unsupported SNMP command: {query.operation.command}"}
            except Timeout as e:
                logger.error(f"SNMP timeout while querying {query.target.host}: {str(e)}")
                return {"error": f"SNMP request timed out. The puresnmp library uses a default timeout."}
            except ConnectionRefusedError as e:
                logger.error(f"Connection refused to {query.target.host}: {str(e)}")
                return {"error": "Connection refused. Verify the device is reachable and SNMP is enabled"}
            except SnmpError as e:
                logger.error(f"SNMP error while querying {query.target.host}: {str(e)}")
                return {"error": f"SNMP error: {str(e)}"}
            except Exception as e:
                logger.error(f"Unexpected error during SNMP query: {str(e)}")
                return {"error": f"Failed to execute SNMP query: {str(e)}"}

            logger.info(f"SNMP query completed successfully")
            return result

        except Exception as e:
            logger.error(f"Error executing SNMP query: {e}", exc_info=True)
            return {"error": f"Error executing SNMP query: {str(e)}"}

    def _prepare_oids(self, operation: SNMPOperation) -> List[str]:
        """Prepare the OIDs for the SNMP query"""
        oids = []

        # Process direct OIDs
        for oid in operation.oids:
            if oid.startswith("."):
                oids.append(oid.lstrip('.'))
            else:
                # Assume it's a named OID, could be in format like 'IF-MIB::ifDescr'
                if "::" in oid:
                    # Try to resolve using MIB service
                    resolved_oid = self.mib_service.resolve_oid(oid)
                    if resolved_oid:
                        oids.append(resolved_oid.lstrip('.'))
                else:
                    # Try to resolve using MIB service
                    resolved_oid = self.mib_service.resolve_oid(oid)
                    if resolved_oid:
                        oids.append(resolved_oid.lstrip('.'))
                    else:
                        # Last resort: treat as raw OID
                        oids.append(oid.lstrip('.'))

        # Process MIB entries
        for mib_name in operation.mib_names:
            # Get all OIDs for this MIB
            mib_oids = self.mib_service.get_mib_oids(mib_name)
            for oid in mib_oids:
                oids.append(oid.lstrip('.'))

        return oids

    async def _execute_get(self, client: Client, oids: List[str]) -> Dict[str, Any]:
        """Execute SNMP GET command"""
        result = {}

        try:
            # Execute a GET for each OID
            for oid in oids:
                try:
                    value = await client.get(ObjectIdentifier(oid))
                    name_str = self.mib_service.translate_oid(oid) or oid
                    result[name_str] = self._format_value(value)
                except SnmpError as e:
                    # Handle all SNMP errors generically since the specific error classes don't exist
                    error_msg = str(e)
                    if "no such object" in error_msg.lower():
                        logger.warning(f"No such object: {oid}")
                        result[oid] = "No such object"
                    elif "no such instance" in error_msg.lower():
                        logger.warning(f"No such instance: {oid}")
                        result[oid] = "No such instance"
                    else:
                        logger.error(f"Error getting OID {oid}: {e}")
                        result[oid] = f"Error: {str(e)}"
                except Exception as e:
                    logger.error(f"Error getting OID {oid}: {e}")
                    result[oid] = f"Error: {str(e)}"

        except Exception as e:
            logger.error(f"Error in GET: {e}")
            if not result:
                # Only set error if we haven't got any results
                result["error"] = str(e)

        return result

    async def _execute_getnext(self, client: Client, oids: List[str]) -> Dict[str, Any]:
        """Execute SNMP GETNEXT command"""
        result = {}

        try:
            # Execute a GETNEXT for each OID
            for oid in oids:
                try:
                    next_oid, value = await client.getnext(ObjectIdentifier(oid))
                    name_str = self.mib_service.translate_oid(f".{next_oid}") or str(next_oid)
                    result[name_str] = self._format_value(value)
                except Exception as e:
                    logger.error(f"Error with GETNEXT for OID {oid}: {e}")
                    result[oid] = f"Error: {str(e)}"

        except Exception as e:
            logger.error(f"Error in GETNEXT: {e}")
            if not result:
                # Only set error if we haven't got any results
                result["error"] = str(e)

        return result

    async def _execute_walk(self, client: Client, oids: List[str]) -> Dict[str, Any]:
        """Execute SNMP WALK command"""
        result = {}

        try:
            # Execute walk for each OID
            for oid in oids:
                try:
                    # client.walk returns an async generator that we need to iterate through
                    walk_gen = client.walk(ObjectIdentifier(oid))

                    # Process results from the generator
                    async for walked_oid, value in walk_gen:
                        name_str = self.mib_service.translate_oid(f".{walked_oid}") or str(walked_oid)
                        result[name_str] = self._format_value(value)
                except Exception as e:
                    logger.error(f"Error with WALK for OID {oid}: {e}")
                    result[f"{oid}_error"] = f"Error: {str(e)}"

        except Exception as e:
            logger.error(f"Error in WALK: {e}")
            if not result:
                # Only set error if we haven't got any results
                result["error"] = str(e)

        return result

    async def _execute_bulk(self, client: Client, oids: List[str],
                            non_repeaters: int = 0, max_repetitions: int = 10) -> Dict[str, Any]:
        """Execute SNMP BULK command"""
        result = {}

        try:
            # Execute bulk for each OID
            for oid in oids:
                bulk_results = await client.bulkget(
                    ObjectIdentifier(oid),
                    scalar_oids=non_repeaters,
                    repeating_oids=max_repetitions
                )

                # Extract all results from the bulk response
                for result_oid, value in bulk_results.items():
                    name_str = self.mib_service.translate_oid(f".{result_oid}") or str(result_oid)
                    result[name_str] = self._format_value(value)

        except Exception as e:
            logger.error(f"Error in BULK: {e}")
            result["error"] = str(e)

        return result

    def _format_value(self, value: Any) -> Any:
        """Format SNMP value into a Python-friendly format"""
        if isinstance(value, bytes):
            try:
                # Try to decode as UTF-8 string
                return value.decode('utf-8')
            except UnicodeDecodeError:
                # If not a string, return hex representation
                return value.hex()
        elif isinstance(value, (int, str, bool, float)):
            return value
        else:
            # For other types, convert to string
            return str(value)
