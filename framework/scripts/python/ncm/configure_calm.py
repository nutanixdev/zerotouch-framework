import time
from copy import deepcopy
from typing import Optional, Dict
from framework.scripts.python.pc.other_ops.change_default_system_password import ChangeDefaultAdminPasswordPc
from framework.scripts.python.pc.other_ops.accept_eula import AcceptEulaPc
from framework.scripts.python.pc.other_ops.update_pulse_pc import UpdatePulsePc
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.script import Script
from framework.scripts.python.pc.create.add_ad_server_pc import AddAdServerPc
from framework.scripts.python.pc.create.add_name_server_pc import AddNameServersPc
from framework.scripts.python.pc.create.add_ntp_server_pc import AddNtpServersPc
from framework.scripts.python.pc.create.create_rolemapping_pc import CreateRoleMappingPc
from framework.helpers.helper_functions import create_pc_objects, read_creds
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class CalmConfig(Script):
    """
    Configure Calm with below configs
    """

    def __init__(self, data: Dict, global_data: Dict, results_key: str = "", log_file: Optional[str] = None, **kwargs):
        self.data = deepcopy(data)
        self.global_data = deepcopy(global_data)
        self.results_key = results_key
        self.log_file = log_file
        super(CalmConfig, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        if not self.data.get("vaults"):
            self.data["vaults"] = self.global_data.get("vaults")
        if not self.data.get("vault_to_use"):
            self.data["vault_to_use"] = self.global_data.get("vault_to_use")

        # calm_credential = self.data.get("ncm_credential")
        # if calm_credential:
        #     # get credentials from the payload
        #     try:
        #         self.data["pc_username"], self.data["pc_password"] = read_creds(data=self.data,
        #                                                                         credential=calm_credential)
        #     except Exception as e:
        #         self.exceptions.append(e)
        #         return

        # Calm is just a PC with different IP
        self.data["pc_ip"] = self.data["ncm_vm_ip"]
        self.data["pc_credential"] = self.data.get("ncm_credential")
        create_pc_objects(self.data, global_data=self.global_data)

        pc_batch_scripts = BatchScript(results_key=self.results_key)

        # Initial PC config
        if "new_pc_admin_credential" in self.data:
            pc_batch_scripts.add(ChangeDefaultAdminPasswordPc(self.data, log_file=self.log_file))
        if "eula" in self.data:
            pc_batch_scripts.add(AcceptEulaPc(self.data, log_file=self.log_file))
        if "enable_pulse" in self.data:
            pc_batch_scripts.add(UpdatePulsePc(self.data, log_file=self.log_file))

        # Add Auth -> needs InitialPcConfig
        if "pc_directory_services" or "directory_services" in self.data:
            # Add Auth -> needs PC config
            pc_batch_scripts.add(AddAdServerPc(self.data, log_file=self.log_file))
            time.sleep(10)

        # Add Role-mappings -> needs AddAdServer
        # Add NTP servers -> InitialPcConfig
        # Add Name servers -> InitialPcConfig
        pc_scripts = BatchScript(parallel=True)
        if "ntp_servers" in self.data:
            pc_scripts.add(AddNtpServersPc(self.data, log_file=self.log_file))
        if "name_servers" in self.data:
            pc_scripts.add(AddNameServersPc(self.data, log_file=self.log_file))
        if "pc_directory_services" or "directory_services" in self.data:
            pc_scripts.add(CreateRoleMappingPc(self.data, log_file=self.log_file))

        if pc_scripts.script_list:
            pc_batch_scripts.add(pc_scripts)

        self.results.update(pc_batch_scripts.run())

    def verify(self):
        pass
