from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.service_group import ServiceGroup
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class DeleteVPC(PcScript):
    """
    Class that deletes VPCs
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.vpcs = self.data.get("vpcs")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(DeleteVPC, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.vpc_util = self.import_helpers_with_version_handling("VPC")

    def execute(self):
        try:
            vpc_name_uuid_dict = self.vpc_util.get_name_uuid_dict()

            if not self.vpcs:
                self.logger.warning(
                    f"No VPCs provided to delete in {self.data['pc_ip']!r}"
                )
                return

            vpcs_to_delete = []
            for vpc_info in self.vpcs:
                if vpc_info["name"] not in vpc_name_uuid_dict:
                    self.logger.warning(f"{vpc_info['name']} doesn't exist in {self.data['pc_ip']!r}!")
                else:
                    vpcs_to_delete.append(
                        self.vpc_util.delete_vpc_spec(
                            vpc_name_uuid_dict[vpc_info["name"]]
                            )
                    )

            if not vpcs_to_delete:
                self.logger.warning(
                    f"No VPCs to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            self.logger.info(f"Trigger batch delete API for service groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.vpc_util.batch_op.batch_delete(
                entity_list=vpcs_to_delete
            )

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of VPCs in PC didn't happen in the prescribed timeframe"
                    )

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.vpcs:
            return

        # Initial status
        self.results["Delete_VPCs"] = {}

        vpc_name_list = []

        for vpc_info in self.vpcs:
            # Initial status
            vpc_name_list = vpc_name_list or self.vpc_util.get_name_list()
            self.results["Delete_VPCs"][vpc_info["name"]] = "CAN'T VERIFY"

            if vpc_info["name"] not in vpc_name_list:
                self.results["Delete_VPCs"][vpc_info["name"]] = "PASS"
            else:
                self.results["Delete_VPCs"][vpc_info["name"]] = "FAIL"
