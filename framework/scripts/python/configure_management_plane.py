import json
from typing import Dict
from .script import Script
from .helpers.batch_script import BatchScript
from .initial_pc_config import InitialPcConfig
from .register_pe_to_pc import RegisterToPc
from .enable_foundation_central import EnableFC
from .generate_fc_api_key import GenerateFcApiKey
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

    @staticmethod
    def config_pc(data):
        """Configure PCs with below configuration to get started with Foundation Central
        """
        block_batch_scripts = BatchScript(results_key="ConfigPC", parallel=True)
        for block_data in data["pod_blocks"]:
            create_pe_objects(block_data)
            create_pc_objects(block_data)
            log_file = f"pc_{block_data['pc_ip']}_configuration.log"
            config_pc_batch_scripts = BatchScript(results_key=block_data['pc_ip'])
            config_pc_batch_scripts.add(InitialPcConfig(block_data, log_file=log_file))
            config_pc_batch_scripts.add(RegisterToPc(block_data, log_file=log_file))
            if block_data.get("enable_fc"):
                config_pc_batch_scripts.add(EnableFC(block_data, log_file=log_file))
            if block_data.get("generate_fc_api_key"): 
                config_pc_batch_scripts.add(GenerateFcApiKey(block_data, log_file=log_file))
            block_batch_scripts.add(config_pc_batch_scripts)
        return block_batch_scripts

    def verify(self):
        pass
