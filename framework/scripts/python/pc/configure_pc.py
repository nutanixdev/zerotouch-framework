import time
from copy import deepcopy
from typing import Optional, Dict
from framework.scripts.python.pc.other_ops.accept_eula import AcceptEulaPc
from framework.scripts.python.pc.other_ops.change_default_system_password import ChangeDefaultAdminPasswordPc
from framework.scripts.python.pc.other_ops.update_pulse_pc import UpdatePulsePc
from framework.scripts.python.pc.create.connect_to_az_pc import ConnectToAz
from framework.scripts.python.pc.create.create_address_groups_pc import CreateAddressGroups
from framework.scripts.python.pc.create.create_pc_categories import CreateCategoryPc
from framework.scripts.python.pc.create.create_protection_policy_pc import CreateProtectionPolicy
from framework.scripts.python.pc.create.create_recovery_plan import CreateRecoveryPlan
from framework.scripts.python.pc.create.create_security_policy_pc import CreateNetworkSecurityPolicy
from framework.scripts.python.pc.create.create_service_groups_pc import CreateServiceGroups
from framework.scripts.python.pc.enable.enable_dr_pc import EnableDR
from framework.scripts.python.pc.enable.enable_flow_pc import EnableMicrosegmentation
from framework.scripts.python.pc.enable.enable_nke_pc import EnableNke
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.script import Script
from framework.scripts.python.pc.create.add_ad_server_pc import AddAdServerPc
from framework.scripts.python.pc.create.add_name_server_pc import AddNameServersPc
from framework.scripts.python.pc.create.add_ntp_server_pc import AddNtpServersPc
from framework.scripts.python.pc.create.create_rolemapping_pc import CreateRoleMappingPc
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import read_creds, create_pc_objects

logger = get_logger(__name__)


class PcConfig(Script):
    """
    Configure PC with below configs
    """

    def __init__(self, data: Dict, global_data: Dict = None, results_key: str = "", log_file: Optional[str] = None,
                 **kwargs):
        self.data = deepcopy(data)
        self.global_data = deepcopy(global_data) if global_data else {}
        self.results_key = results_key
        self.log_file = log_file
        super(PcConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            if not self.data.get("vaults"):
                self.data["vaults"] = self.global_data.get("vaults")
            if not self.data.get("vault_to_use"):
                self.data["vault_to_use"] = self.global_data.get("vault_to_use")

            # block_credential = self.data.get("pc_credential")
            # # get credentials from the payload
            # if block_credential:
            #     try:
            #         self.data["pc_username"], self.data["pc_password"] = read_creds(data=self.data,
            #                                                                         credential=block_credential)
            #     except Exception as e:
            #         self.exceptions.append(e)
            #         return

            # Get PC session
            if not self.data.get("pc_session"):
                create_pc_objects(self.data, global_data=self.global_data)

            pc_batch_scripts = BatchScript(results_key=self.results_key)

            # Initial PC config
            # Assumed this is already taken care in management config
            if "new_pc_admin_credential" in self.data:
                pc_batch_scripts.add(ChangeDefaultAdminPasswordPc(self.data, log_file=self.log_file))
            if "eula" in self.data:
                pc_batch_scripts.add(AcceptEulaPc(self.data, log_file=self.log_file))
            if "enable_pulse" in self.data:
                pc_batch_scripts.add(UpdatePulsePc(self.data, log_file=self.log_file))

            if "pc_directory_services" in self.data or "directory_services" in self.data:
                # Add Auth -> needs PC config
                pc_batch_scripts.add(AddAdServerPc(self.data, log_file=self.log_file))
                time.sleep(10)

            # Add Role-mappings -> needs AddAdServer
            # Add NTP servers -> InitialPcConfig
            # Add Name servers -> InitialPcConfig
            pc_enable_scripts = BatchScript(parallel=True)
            if "enable_microsegmentation" in self.data:
                pc_enable_scripts.add(EnableMicrosegmentation(self.data, log_file=self.log_file))
            if "enable_dr" in self.data:
                pc_enable_scripts.add(EnableDR(self.data, log_file=self.log_file))
            if "enable_nke" in self.data:
                pc_enable_scripts.add(EnableNke(self.data, log_file=self.log_file))
            if "remote_azs" in self.data:
                pc_enable_scripts.add(ConnectToAz(self.data, log_file=self.log_file))
            if "ntp_servers_list" in self.data or "pc_ntp_servers_list" in self.data:
                pc_enable_scripts.add(AddNtpServersPc(self.data, log_file=self.log_file))
            if "name_servers_list" in self.data or "pc_name_servers_list" in self.data:
                pc_enable_scripts.add(AddNameServersPc(self.data, log_file=self.log_file))
            if "pc_directory_services" in self.data or "directory_services" in self.data:
                pc_enable_scripts.add(CreateRoleMappingPc(self.data, log_file=self.log_file))

            if pc_enable_scripts.script_list:
                pc_batch_scripts.add(pc_enable_scripts)

            # Entities without any dependencies
            # Create Categories in PC
            # Create AddressGroups
            # Create ServiceGroups
            pc_create_scripts = BatchScript(parallel=True)
            if "categories" in self.data:
                pc_create_scripts.add(CreateCategoryPc(self.data, log_file=self.log_file))
            if "address_groups" in self.data:
                pc_create_scripts.add(CreateAddressGroups(self.data, log_file=self.log_file))
            if "service_groups" in self.data:
                pc_create_scripts.add(CreateServiceGroups(self.data, log_file=self.log_file))

            if pc_create_scripts.script_list:
                pc_batch_scripts.add(pc_create_scripts)

            # Entities with dependencies
            # Add Security Policies -> needs CreateAddressGroups, CreateServiceGroups
            # create PP -> needs EnableDR
            pc_dependant_scripts = BatchScript(parallel=True)
            if "security_policies" in self.data:
                pc_dependant_scripts.add(CreateNetworkSecurityPolicy(self.data, log_file=self.log_file))
            if "protection_rules" in self.data:
                pc_dependant_scripts.add(CreateProtectionPolicy(self.data, log_file=self.log_file))

            if pc_dependant_scripts.script_list:
                pc_batch_scripts.add(pc_dependant_scripts)

            # create RP -> needs CreateProtectionPolicy
            if "recovery_plans" in self.data:
                pc_batch_scripts.add(CreateRecoveryPlan(self.data, log_file=self.log_file))
            self.results.update(pc_batch_scripts.run())
            self.data["json_output"] = self.results
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        pass
