import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.service_group import ServiceGroup
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteServiceGroups(Script):
    """
    Class that deletes Service Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.service_groups = self.data.get("service_groups")
        self.pc_session = self.data["pc_session"]
        super(DeleteServiceGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            service_group = ServiceGroup(self.pc_session)
            service_group_list = service_group.list(length=10000)
            service_group_name_uuid_dict = {
                sg.get("service_group", {}).get("name"): sg.get("uuid")
                for sg in service_group_list
                if sg.get("service_group", {}).get("name")
            }

            if not self.service_groups:
                self.logger.warning(
                    f"No service_groups to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            sgs_to_delete = []
            for sg in self.service_groups:
                if sg["name"] not in service_group_name_uuid_dict:
                    self.logger.warning(f"{sg['name']} doesn't exist!")
                else:
                    sgs_to_delete.append(service_group_name_uuid_dict[sg["name"]])

            if not sgs_to_delete:
                self.logger.warning(
                    f"No service_groups to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            self.logger.info(f"Trigger batch delete API for service groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = service_group.batch_op.batch_delete(
                entity_list=sgs_to_delete
            )

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session, task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Service groups in PC didn't happen in the prescribed timeframe"
                    )

        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.service_groups:
            return

        # Initial status
        self.results["Delete_Service_groups"] = {}

        service_group = ServiceGroup(self.pc_session)
        service_group_list = []
        service_group_name_list = []

        for sg in self.service_groups:
            # Initial status
            self.results["Delete_Service_groups"][sg["name"]] = "CAN'T VERIFY"

            service_group_list = service_group_list or service_group.list(length=10000)
            service_group_name_list = service_group_name_list or [
                service_group.get("service_group", {}).get("name")
                for service_group in service_group_list
                if service_group.get("service_group", {}).get("name")
            ]
            if sg["name"] not in service_group_name_list:
                self.results["Delete_Service_groups"][sg["name"]] = "PASS"
            else:
                self.results["Delete_Service_groups"][sg["name"]] = "FAIL"
