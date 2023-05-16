import time
from copy import deepcopy
from helpers.helper_functions import create_pe_pc_objects
from scripts.python.add_ad_server_pe import AddAdServerPe
from scripts.python.connect_to_az_pc import ConnectToAz
from scripts.python.create_address_groups_pc import CreateAddressGroups
from scripts.python.create_container_pe import CreateContainerPe
from scripts.python.create_pc_categories import CreateCategoryPc
from scripts.python.create_pc_subnets import CreateSubnetsPc
from scripts.python.create_protection_policy_pc import CreateProtectionPolicy
from scripts.python.create_recovery_plan import CreateRecoveryPlan
from scripts.python.create_rolemapping_pe import CreateRoleMapping
from scripts.python.create_security_policy_pc import CreateNetworkSecurityPolicy
from scripts.python.create_service_groups_pc import CreateServiceGroups
from scripts.python.enable_leap_pc import EnableLeap
from scripts.python.enable_microseg_pc import EnableMicroseg
from scripts.python.helpers.batch_script import BatchScript
from scripts.python.initial_cluster_config import InitialClusterConfig
from scripts.python.register_pe_to_pc import RegisterToPc
from scripts.python.script import Script
from helpers.log_utils import get_logger
from scripts.python.update_dsip_pe import UpdateDsip

logger = get_logger(__name__)


class PodConfig(Script):
    """
    Configure Pods with below configs
    """
    def __init__(self, data: dict):
        self.parent_batch_scripts = None
        self.data = data
        self.pods = self.data["pods"]
        super(PodConfig, self).__init__()

    def execute(self):
        start = time.time()
        for pod in self.pods:
            self.parent_batch_scripts = {}
            for az, az_values in pod.items():
                # Create a parent Batch script for each AZ, run sequentially
                self.parent_batch_scripts[az] = BatchScript()
                # Create PC session for each AZ, PE sessions for all the clusters
                create_pe_pc_objects(az_values)
                # Get primary scripts
                self.parent_batch_scripts[az].add(self.primary_scripts(az_values))
                # Get cluster update scripts
                self.parent_batch_scripts[az].add(self.cluster_update_scripts(az_values))
                # Get secondary scripts
                self.parent_batch_scripts[az].add(self.secondary_scripts(az_values))
                # Get tertiary scripts
                self.parent_batch_scripts[az].add(self.tertiary_scripts(az_values))
                # Get DR scripts
                self.parent_batch_scripts[az].add(self.configure_dr_scripts(az_values))

        for pod in self.pods:
            for az in pod.keys():
                self.parent_batch_scripts[az].run()

        total_time = time.time() - start
        logger.info(f"Total time: {total_time:.2f} seconds")

    @staticmethod
    def primary_scripts(data: dict) -> BatchScript:
        primary_batch_scripts = BatchScript(parallel=True)
        # Enable Flow in PC
        # Create Categories in PC
        # Create AZs in PC
        # Initial cluster config in all clusters

        data = deepcopy(data)
        scripts = [EnableMicroseg(data),
                   CreateCategoryPc(data),
                   ConnectToAz(data),
                   InitialClusterConfig(data)]
        primary_batch_scripts.add_all(scripts)
        return primary_batch_scripts

    @staticmethod
    def cluster_update_scripts(data: dict) -> BatchScript:
        cluster_scripts = BatchScript()
        # Add Auth -> needs InitialClusterConfig
        cluster_scripts.add(AddAdServerPe(data))
        return cluster_scripts

    @staticmethod
    def secondary_scripts(data: dict) -> BatchScript:
        secondary_batch_scripts = BatchScript(parallel=True)
        # Register PE to PC -> needs InitialClusterConfig
        # Create containers in PE -> needs InitialClusterConfig
        # Update DSIP -> needs InitialClusterConfig, fails if we update DSIP with Auth
        # Create AddressGroups -> needs RegisterToPc
        # Create ServiceGroups -> needs RegisterToPc

        data = deepcopy(data)
        scripts = [RegisterToPc(data),
                   CreateContainerPe(data),
                   UpdateDsip(data),
                   CreateAddressGroups(data),
                   CreateServiceGroups(data)]
        secondary_batch_scripts.add_all(scripts)
        return secondary_batch_scripts

    @staticmethod
    def tertiary_scripts(data: dict) -> BatchScript:
        tertiary_batch_scripts = BatchScript(parallel=True)
        # Create Subnets in PC -> needs RegisterToPc
        # Add Role-mappings -> needs AddAdServer
        # Add Security Policies -> needs CreateAddressGroups, CreateServiceGroups
        # Enable Leap -> Needs UpdateDsip

        data = deepcopy(data)
        scripts = [CreateSubnetsPc(data),
                   CreateRoleMapping(data),
                   CreateNetworkSecurityPolicy(data),
                   EnableLeap(data)]
        tertiary_batch_scripts.add_all(scripts)
        return tertiary_batch_scripts

    @staticmethod
    def configure_dr_scripts(data: dict) -> BatchScript:
        quaternary_batch_scripts = BatchScript()
        # create PP -> needs EnableLeap
        # create RP -> needs CreateProtectionPolicy

        data = deepcopy(data)
        scripts = [CreateProtectionPolicy(data),
                   CreateRecoveryPlan(data)]
        quaternary_batch_scripts.add_all(scripts)
        return quaternary_batch_scripts

    def verify(self):
        pass
