import json
from typing import Dict
from framework.scripts.python.pc.other_ops.change_default_system_password import ChangeDefaultAdminPasswordPc
from framework.scripts.python.pc.other_ops.accept_eula import AcceptEulaPc
from framework.scripts.python.pc.other_ops.update_pulse_pc import UpdatePulsePc
from .script import Script
from .helpers.batch_script import BatchScript
from framework.scripts.python.pe.other_ops.register_pe_to_pc import RegisterToPc
from framework.scripts.python.pc.enable.enable_foundation_central import EnableFC
from framework.scripts.python.pc.fc.generate_fc_api_key import GenerateFcApiKey
from framework.helpers.helper_functions import create_pe_objects, create_pc_objects
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class ConfigManagementPlane(Script):
    """
    Configure Management Plane with below configs
    """

    def __init__(self, data: Dict, **kwargs):
        self.results = {}
        self.data = data
        self.pod = self.data["pod"]
        self.config_management_plane_scripts = None
        super(ConfigManagementPlane, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        # Scripts to execute Management Plane configuration
        if self.pod.get("pod_blocks"):
            self.config_management_plane_scripts = self.config_pc(self.pod)

            # Run configuration
            result = self.config_management_plane_scripts.run()
            self.logger.info(json.dumps(result, indent=4))
        else:
            self.exceptions.append("No Pod Blocks to configure")

    def config_pc(self, data):
        """Configure PCs with below configuration to get started with Foundation Central
        """
        block_batch_scripts = BatchScript(results_key="ConfigPC", parallel=True)
        for block_data in data["pod_blocks"]:
            create_pe_objects(block_data, global_data=self.data)
            create_pc_objects(block_data, global_data=self.data)
            log_file = f"pc_{block_data['pc_ip']}_configuration.log"
            config_pc_batch_scripts = BatchScript(results_key=block_data['pc_ip'])
            block_data["vaults"] = self.data["vaults"]
            block_data["vault_to_use"] = self.data["vault_to_use"]
            config_pc_batch_scripts.add_all([
                ChangeDefaultAdminPasswordPc(block_data, log_file=log_file),
                AcceptEulaPc(block_data, log_file=log_file),
                UpdatePulsePc(block_data, log_file=log_file)
            ])
            config_pc_batch_scripts.add(RegisterToPc(block_data, log_file=log_file))
            if block_data.get("enable_fc"):
                config_pc_batch_scripts.add(EnableFC(block_data, log_file=log_file))
            if block_data.get("generate_fc_api_key"): 
                config_pc_batch_scripts.add(GenerateFcApiKey(block_data, log_file=log_file))
            block_batch_scripts.add(config_pc_batch_scripts)
        return block_batch_scripts

    def verify(self):
        pass
