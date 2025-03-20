import asyncio
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from puresnmp import Client, V1, V2C, ObjectIdentifier
from puresnmp.exc import SnmpError

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

            # Execute SNMP command
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

            logger.info(f"SNMP query completed successfully")
            return result

        except SnmpError as e:
            logger.error(f"SNMP error: {e}")
            return {"error": f"SNMP error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error executing SNMP query: {e}")
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
            # Execute the gets in parallel for multiple OIDs
            tasks = []
            for oid in oids:
                tasks.append(client.get(ObjectIdentifier(oid)))

            # Await all get operations
            values = await asyncio.gather(*tasks)

            # Map results back to OIDs
            for i, oid in enumerate(oids):
                name_str = self.mib_service.translate_oid(f".{oid}") or oid
                result[name_str] = self._format_value(values[i])

        except Exception as e:
            logger.error(f"Error in GET: {e}")
            result["error"] = str(e)

        return result

    async def _execute_getnext(self, client: Client, oids: List[str]) -> Dict[str, Any]:
        """Execute SNMP GETNEXT command"""
        result = {}

        try:
            # Execute getnext for each OID
            for oid in oids:
                next_results = await client.getnext(ObjectIdentifier(oid))
                for next_oid, value in next_results.items():
                    name_str = self.mib_service.translate_oid(f".{next_oid}") or str(next_oid)
                    result[name_str] = self._format_value(value)

        except Exception as e:
            logger.error(f"Error in GETNEXT: {e}")
            result["error"] = str(e)

        return result

    async def _execute_walk(self, client: Client, oids: List[str]) -> Dict[str, Any]:
        """Execute SNMP WALK command"""
        result = {}

        try:
            # Execute walk for each OID
            for oid in oids:
                # client.walk returns an async generator that we need to iterate through
                walk_gen = client.walk(ObjectIdentifier(oid))

                # Process results from the generator
                async for walked_oid, value in walk_gen:
                    name_str = self.mib_service.translate_oid(f".{walked_oid}") or str(walked_oid)
                    result[name_str] = self._format_value(value)

        except Exception as e:
            logger.error(f"Error in WALK: {e}")
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
