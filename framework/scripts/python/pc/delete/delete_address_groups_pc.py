import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.address_group import AddressGroup
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteAddressGroups(Script):
    """
    Class that deletes Address Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        super(DeleteAddressGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            address_group = AddressGroup(self.pc_session)
            address_group_list = address_group.list()
            address_group_name_uuid_dict = {
                ag.get("address_group", {}).get("name"): ag.get("uuid")
                for ag in address_group_list
                if ag.get("address_group", {}).get("name")
            }

            if not self.address_groups:
                self.logger.warning(f"No Address Groups to delete in {self.data['pc_ip']!r}. Skipping...")
                return

            ags_to_delete_uuids = []
            for ag in self.address_groups:
                if ag["name"] not in address_group_name_uuid_dict.keys():
                    self.logger.warning(f"{ag['name']!r} Address Group doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    self.logger.info(f"Deleting Address Group {ag['name']!r} in {self.data['pc_ip']!r}")
                    ags_to_delete_uuids.append(address_group_name_uuid_dict[ag['name']])
                except Exception as e:
                    self.exceptions.append(f"Failed to delete address_group {ag['name']!r}: {e}")

            if not ags_to_delete_uuids:
                self.logger.warning(f"No Address Groups to delete in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch delete API for Address groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = address_group.batch_op.batch_delete(entity_list=ags_to_delete_uuids)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session, task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Security policies in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.address_groups:
            return

        # Initial status
        self.results["Delete_Address_groups"] = {}

        time.sleep(5)
        address_group = AddressGroup(self.pc_session)
        address_group_list = []
        address_group_name_list = []

        for ag in self.address_groups:
            # Initial status
            self.results["Delete_Address_groups"][ag.get("name")] = "CAN'T VERIFY"
            address_group_list = address_group_list or address_group.list()
            address_group_name_list = address_group_name_list or [
                ag.get("address_group", {}).get("name")
                for ag in address_group_list
                if ag.get("address_group", {}).get("name")
            ]

            if ag["name"] not in address_group_name_list:
                self.results["Delete_Address_groups"][ag["name"]] = "PASS"
            else:
                self.results["Delete_Address_groups"][ag["name"]] = "FAIL"
