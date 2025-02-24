from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class CreateVPC(PcScript):
    """
    Class that creates VPCs
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.vpcs = self.data.get("vpcs")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(CreateVPC, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.vpc_util = self.import_helpers_with_version_handling("VPC")

    def execute(self):
        try:
            if not self.vpcs:
                self.logger.warning(f"No VPCs to create in {self.data['pc_ip']!r}. Skipping...")
                return

            vpc_name_list = self.vpc_util.get_name_list()
            
            vpcs_to_create = []
            for vpc_info in self.vpcs:
                if vpc_info["name"] in vpc_name_list:
                    self.logger.warning(f"VPC with Name {vpc_info['name']} already exists!")
                    continue
                try:
                    vpcs_to_create.append(self.vpc_util.create_vpc_spec(vpc_info))
                except Exception as e:
                    self.exceptions.append(f"Failed to create VPC {vpc_info['name']}: {e}")

            if not vpcs_to_create:
                self.logger.warning(f"No VPCs to create in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch create API for VPCs in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.vpc_util.batch_op.batch_create(request_payload_list=vpcs_to_create)
            
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of VPCs in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.vpcs:
            return

        # Initial status
        self.results["Create_VPCs"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        vpc_name_list = []

        for vpc_info in self.vpcs:
            vpc_name_list = vpc_name_list or self.vpc_util.get_name_list()
            self.results["Create_VPCs"][vpc_info["name"]] = "CAN'T VERIFY"
    
            if vpc_info["name"] in vpc_name_list:
                self.results["Create_VPCs"][vpc_info["name"]] = "PASS"
            else:
                self.results["Create_VPCs"][vpc_info["name"]] = "FAIL"
