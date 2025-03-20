import os
import glob
import re
from typing import Dict, List, Optional, Set
from loguru import logger

from app.core.config import config
from app.utils.cache import get_cache, set_cache


class MIBService:
    def __init__(self):
        """Initialize the MIB service with simplified functionality"""
        self.mib_dir = config.mib_directory
        self.oid_name_cache: Dict[str, str] = {}  # Cache for OID to name translation
        self.name_oid_cache: Dict[str, str] = {}  # Cache for name to OID translation
        self.loaded_mibs: Set[str] = set()  # Names of loaded MIBs

        # Create MIB directory if it doesn't exist
        os.makedirs(self.mib_dir, exist_ok=True)

        # Basic MIB mapping for common OIDs
        self._init_basic_mibs()

    def _init_basic_mibs(self):
        """Initialize with basic MIB data for common OIDs"""
        # System MIB
        self.name_oid_cache["SNMPv2-MIB::sysDescr.0"] = "1.3.6.1.2.1.1.1.0"
        self.name_oid_cache["SNMPv2-MIB::sysObjectID.0"] = "1.3.6.1.2.1.1.2.0"
        self.name_oid_cache["SNMPv2-MIB::sysUpTime.0"] = "1.3.6.1.2.1.1.3.0"
        self.name_oid_cache["SNMPv2-MIB::sysContact.0"] = "1.3.6.1.2.1.1.4.0"
        self.name_oid_cache["SNMPv2-MIB::sysName.0"] = "1.3.6.1.2.1.1.5.0"
        self.name_oid_cache["SNMPv2-MIB::sysLocation.0"] = "1.3.6.1.2.1.1.6.0"
        self.name_oid_cache["SNMPv2-MIB::sysServices.0"] = "1.3.6.1.2.1.1.7.0"

        # Interface MIB
        self.name_oid_cache["IF-MIB::ifNumber.0"] = "1.3.6.1.2.1.2.1.0"
        self.name_oid_cache["IF-MIB::ifIndex"] = "1.3.6.1.2.1.2.2.1.1"
        self.name_oid_cache["IF-MIB::ifDescr"] = "1.3.6.1.2.1.2.2.1.2"
        self.name_oid_cache["IF-MIB::ifType"] = "1.3.6.1.2.1.2.2.1.3"
        self.name_oid_cache["IF-MIB::ifMtu"] = "1.3.6.1.2.1.2.2.1.4"
        self.name_oid_cache["IF-MIB::ifSpeed"] = "1.3.6.1.2.1.2.2.1.5"
        self.name_oid_cache["IF-MIB::ifPhysAddress"] = "1.3.6.1.2.1.2.2.1.6"
        self.name_oid_cache["IF-MIB::ifAdminStatus"] = "1.3.6.1.2.1.2.2.1.7"
        self.name_oid_cache["IF-MIB::ifOperStatus"] = "1.3.6.1.2.1.2.2.1.8"
        self.name_oid_cache["IF-MIB::ifInOctets"] = "1.3.6.1.2.1.2.2.1.10"
        self.name_oid_cache["IF-MIB::ifOutOctets"] = "1.3.6.1.2.1.2.2.1.16"

        # Build reverse mapping
        for name, oid in self.name_oid_cache.items():
            self.oid_name_cache[oid] = name

        # Add standard MIBs to loaded list
        self.loaded_mibs.add("SNMPv2-MIB")
        self.loaded_mibs.add("IF-MIB")

    def get_loaded_mibs(self) -> List[str]:
        """Get a list of loaded MIB names"""
        return list(self.loaded_mibs)

    def resolve_oid(self, name: str) -> Optional[str]:
        """Resolve a symbolic name to an OID"""
        # Check cache first
        if name in self.name_oid_cache:
            return self.name_oid_cache[name]

        # Handle index notation (e.g., ifDescr.1)
        if "." in name and not name.startswith("."):
            base_name, index = name.split(".", 1)
            if base_name in self.name_oid_cache:
                return f"{self.name_oid_cache[base_name]}.{index}"

        return None

    def translate_oid(self, oid: str) -> Optional[str]:
        """Translate an OID to a symbolic name"""
        # Check exact match in cache first
        if oid in self.oid_name_cache:
            return self.oid_name_cache[oid]

        # Try to match base OIDs
        for known_oid, known_name in self.oid_name_cache.items():
            if oid.startswith(known_oid + "."):
                suffix = oid[len(known_oid):]
                base_name = known_name.split(".")[0]  # Remove any existing index
                return f"{base_name}{suffix}"

        return None

    def get_mib_oids(self, mib_name: str) -> List[str]:
        """Get all OIDs defined in a specific MIB"""
        cache_key = f"mib_oids_{mib_name}"
        cached_oids = get_cache(cache_key)

        if cached_oids:
            return cached_oids

        oids = []
        # Return OIDs that belong to this MIB
        for name, oid in self.name_oid_cache.items():
            if name.startswith(f"{mib_name}::"):
                oids.append(oid)

        # Cache the results
        if oids:
            set_cache(cache_key, oids)

        return oids

    def add_mib_file(self, file_path: str) -> bool:
        """Add a new MIB file to the MIB directory (simplified handling)"""
        try:
            # Copy MIB file to MIB directory
            file_name = os.path.basename(file_path)
            target_path = os.path.join(self.mib_dir, file_name)

            if os.path.exists(file_path) and os.path.isfile(file_path):
                with open(file_path, 'rb') as src_file:
                    mib_content = src_file.read()

                with open(target_path, 'wb') as dest_file:
                    dest_file.write(mib_content)

                # Add MIB name to loaded list
                mib_name = os.path.splitext(file_name)[0]
                self.loaded_mibs.add(mib_name)

                logger.info(f"MIB file added: {file_name}")
                return True
            else:
                logger.error(f"MIB file not found: {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error adding MIB file: {e}")
            return False
