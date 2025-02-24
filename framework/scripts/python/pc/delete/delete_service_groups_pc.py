from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class DeleteServiceGroups(PcScript):
    """
    Class that deletes Service Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.service_groups = self.data.get("service_groups")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(DeleteServiceGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.service_group_helper = self.import_helpers_with_version_handling("ServiceGroup")

    def execute(self):
        try:
            service_group_name_uuid_dict = self.service_group_helper.get_name_uuid_dict()

            if not self.service_groups:
                self.logger.warning(
                    f"No service_groups provided to delete in {self.data['pc_ip']!r}"
                )
                return

            sgs_to_delete = []
            for sg in self.service_groups:
                if sg["name"] not in service_group_name_uuid_dict:
                    self.logger.warning(f"{sg['name']} doesn't exist in {self.data['pc_ip']!r}!")
                else:
                    sgs_to_delete.append(
                        self.service_group_helper.delete_service_group_spec(
                            service_group_name_uuid_dict[sg["name"]]
                            )
                    )

            if not sgs_to_delete:
                self.logger.warning(
                    f"No service_groups to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            self.logger.info(f"Trigger batch delete API for service groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.service_group_helper.batch_op.batch_delete(
                entity_list=sgs_to_delete
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
                        "Timed out. Deletion of Service groups in PC didn't happen in the prescribed timeframe"
                    )

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.service_groups:
            return

        # Initial status
        self.results["Delete_Service_groups"] = {}

        service_group_name_list = []

        for sg in self.service_groups:
            # Initial status
            service_group_name_list = service_group_name_list or self.service_group_helper.get_name_list() 
            self.results["Delete_Service_groups"][sg["name"]] = "CAN'T VERIFY"

            if sg["name"] not in service_group_name_list:
                self.results["Delete_Service_groups"][sg["name"]] = "PASS"
            else:
                self.results["Delete_Service_groups"][sg["name"]] = "FAIL"
