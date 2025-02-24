from abc import abstractmethod
from framework.helpers.log_utils import get_logger
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.v3.prism_central import PrismCentral
from packaging.version import parse

import importlib

logger = get_logger(__name__)

# Map of entities with Threshold version from which it uses v4 and module name
ENTITY_VERSION_MAP = {
    "SecurityPolicy": ("pc.2024.3", "security_rule"),
    "AddressGroup": ("pc.2024.3", "address_group"),
    "ServiceGroup": ("pc.2024.3", "service_group"),
    "Category": ("pc.2024.3", "category"),
    "Task": ("pc.2024.3", "task"),
    "VPC": ("pc.2024.3", "vpc"),
    "Application": ("default", "application"),
    "AvailabilityZone": ("default", "availabilty_zone"),
    "Blueprint": ("default", "blueprint"),
    "CloudTrust": ("default", "cloud_trust"),
    "Cluster": ("default", "cluster"),
    "IdentityProvider": ("default", "identity_provider"),
    "Image": ("default", "image"),
    "Network": ("default", "network"),
    "Ova": ("default", "ova"),
    "PrismCentral": ("default", "prism_central"),
    "ProtectionRule": ("default", "protection_rule"),
    "RecoveryPlan": ("default", "recovery_plan"),
    "RemoteSyslog": ("default", "syslog"),
    "VM": ("default", "vm"),
    "NetworkController": ("pc.2024.3", "network_controller"),
}

class PcScript(Script):
    def __init__(self, **kwargs):
        if not self.data.get("pc_version"):
            self.data["pc_version"] = self.get_pc_version()
        super(PcScript, self).__init__(**kwargs)

    def get_pc_version(self):
        try:
            pc = PrismCentral(self.pc_session)
            pc_data = pc.read()
            return pc_data['resources']['version']
        except Exception as e:
            logger.error(f"Failed to get PC version with Unexpected Error: {e}")
            return "default"

    @staticmethod
    def compare_versions(pc_version, threshold_version):
        # Return True if pc_version is greater than or equal to threshold_version for v4 implementation
        if threshold_version == "default":
            return False
        if not pc_version.startswith("pc"):
            # If the version is not in the format pc.x.x.x or pc.x.x, return False
            return False

        # Strip the "pc." prefix for version comparison
        pc_version_number = pc_version[3:]
        threshold_version_number = threshold_version[3:]

        # Use `packaging.version.parse` to compare the versions
        return parse(pc_version_number) >= parse(threshold_version_number)


    def import_helpers_with_version_handling(self, entity):
        # Determine which entities should use v4 based on the current build version
        if PcScript.compare_versions(self.data['pc_version'], ENTITY_VERSION_MAP[entity][0]):
            # Import helper for entity using v4
            module = f"framework.scripts.python.helpers.v4.{ENTITY_VERSION_MAP[entity][1]}"
            cls = getattr(importlib.import_module(module),entity)
            return cls(self.v4_api_util)
        else:
            # Import helper for entity using v3
            module = f"framework.scripts.python.helpers.v3.{ENTITY_VERSION_MAP[entity][1]}"
            cls = getattr(importlib.import_module(module),entity)
            return cls(self.pc_session)

    @abstractmethod
    def execute(self, **kwargs):
        pass

    @abstractmethod
    def verify(self, **kwargs):
        pass