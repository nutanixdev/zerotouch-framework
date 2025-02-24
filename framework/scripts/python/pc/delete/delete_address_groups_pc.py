import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.address_group import AddressGroup
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class DeleteAddressGroups(PcScript):
    """
    Class that deletes Address Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(DeleteAddressGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.address_group_util = self.import_helpers_with_version_handling("AddressGroup")

    def execute(self):
        try:
            address_group_name_uuid_dict = self.address_group_util.get_name_uuid_dict()

            if not self.address_groups:
                self.logger.warning(f"No Address Groups to delete in {self.data['pc_ip']!r}")
                return

            ags_to_delete = []
            for ag in self.address_groups:
                if ag["name"] not in address_group_name_uuid_dict:
                    self.logger.warning(f"{ag['name']!r} Address Group doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    self.logger.info(f"Deleting Address Group {ag['name']!r} in {self.data['pc_ip']!r}")
                    ags_to_delete.append(
                        self.address_group_util.delete_address_group_spec(
                            address_group_name_uuid_dict[ag['name']]
                            )
                    )
                except Exception as e:
                    self.exceptions.append(f"Failed to delete address_group {ag['name']!r}: {e}")

            if not ags_to_delete:
                self.logger.warning(f"No Address Groups to delete in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch delete API for Address groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.address_group_util.batch_op.batch_delete(
                entity_list= ags_to_delete
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
                        "Timed out. Deletion of Address Groups in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.address_groups:
            return

        # Initial status
        self.results["Delete_Address_groups"] = {}

        time.sleep(5)
        address_group_name_list = []
        for ag in self.address_groups:
            
            address_group_name_list = address_group_name_list or self.address_group_util.get_name_list()
            self.results["Delete_Address_groups"][ag.get("name")] = "CAN'T VERIFY"

            if ag["name"] not in address_group_name_list:
                self.results["Delete_Address_groups"][ag["name"]] = "PASS"
            else:
                self.results["Delete_Address_groups"][ag["name"]] = "FAIL"
