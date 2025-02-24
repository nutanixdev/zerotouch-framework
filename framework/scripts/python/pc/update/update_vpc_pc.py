from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class UpdateVPC(PcScript):
    """
    Class that modifies VPCs using name as the unique identifier
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.vpcs = self.data.get("vpcs")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(UpdateVPC, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.vpc_util = self.import_helpers_with_version_handling("VPC")

    def execute(self):
        try:
            if not self.vpcs:
                self.logger.warning(f"No VPCs to provided to modify in {self.data['pc_ip']!r}")
                return

            vpc_name_uuid_dict = self.vpc_util.get_name_uuid_dict()
            vpcs_to_update = []

            for vpc_info in self.vpcs:
                if vpc_info["name"] not in vpc_name_uuid_dict.keys():
                    self.logger.warning(f"VPC with name {vpc_info['name']} doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    vpc_object = self.vpc_util.get_by_ext_id(vpc_name_uuid_dict[vpc_info["name"]])
                    vpcs_to_update.append(self.vpc_util.update_vpc_spec(vpc_info, vpc_object.data))
                except Exception as e:
                    self.exceptions.append(f"Failed to update VPC {vpc_info['name']}: {e}")

            if not vpcs_to_update:
                self.logger.warning(f"No VPCs to update in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch update API for service groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.vpc_util.batch_op.batch_update(entity_update_list=vpcs_to_update)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Updation of VPCs in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.vpcs:
            return

        # Initial status
        self.results["Update_VPCs"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification

        for vpc_info in self.vpcs:
            # Initial status
            vpc_name_list = self.vpc_utils.get_name_list()
            self.results["Update_VPCs"][vpc_info["name"]] = "CAN'T VERIFY"
            name = (vpc_info["new_name"] if vpc_info.get("new_name") else vpc_info["name"])

            if name in vpc_name_list:
                self.results["Update_VPCs"][vpc_info["name"]] = "PASS"
            else:
                self.results["Update_VPCs"][vpc_info["name"]] = "FAIL"
