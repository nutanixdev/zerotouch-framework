from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.service_group import ServiceGroup
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class UpdateServiceGroups(PcScript):
    """
    Class that modifies Service Groups using name as the unique identifier
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.service_groups = self.data.get("service_groups")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(UpdateServiceGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.service_group_util = self.import_helpers_with_version_handling("ServiceGroup")

    def execute(self):
        try:
            if not self.service_groups:
                self.logger.warning(f"No service_groups to provided to modify in {self.data['pc_ip']!r}")
                return

            service_group_name_uuid_dict = self.service_group_util.get_name_uuid_dict()
            sgs_to_update = []

            for sg in self.service_groups:
                if sg["name"] not in service_group_name_uuid_dict.keys():
                    self.logger.warning(f"Service group with name {sg['name']} doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    service_group_object = self.service_group_util.get_by_ext_id(service_group_name_uuid_dict[sg["name"]])
                    sgs_to_update.append(self.service_group_util.update_service_group_spec(sg, service_group_object.data))
                except Exception as e:
                    self.exceptions.append(f"Failed to update Service Group {sg['name']}: {e}")

            if not sgs_to_update:
                self.logger.warning(f"No service_groups to create in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch update API for service groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.service_group_util.batch_op.batch_update(entity_update_list=sgs_to_update)
            
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Updation of Service Groups in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.service_groups:
            return

        # Initial status
        self.results["Update_Service_groups"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        service_group_name_list = []

        for sg in self.service_groups:
            service_group_name_list = service_group_name_list or self.service_group_util.get_name_list()

            self.results["Update_Service_groups"][sg["name"]] = "CAN'T VERIFY"
            name = (sg["new_name"] if sg.get("new_name") else sg["name"])

            if name in service_group_name_list:
                self.results["Update_Service_groups"][sg["name"]] = "PASS"
            else:
                self.results["Update_Service_groups"][sg["name"]] = "FAIL"
