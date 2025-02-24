import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class UpdateAddressGroups(PcScript):
    """
    Class that updates Address Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(UpdateAddressGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.address_group_util = self.import_helpers_with_version_handling("AddressGroup")

    def execute(self):
        try:
            if not self.address_groups:
                self.logger.warning(f"No address group provided to modify in {self.data['pc_ip']!r}")
                return

            address_group_name_uuid_dict = self.address_group_util.get_name_uuid_dict()

            ags_to_update = []
            for ag in self.address_groups:
                if ag["name"] not in address_group_name_uuid_dict.keys():
                    self.logger.warning(f"Address group with name {ag['name']} doesn't exist in {self.data['pc_ip']!r}!")
                    continue
                try:
                    self.logger.info(f"Updating Address Group '{ag['name']}' in {self.data['pc_ip']!r}")
                    address_group_object = self.address_group_util.get_by_ext_id(address_group_name_uuid_dict[ag["name"]])
                    ags_to_update.append(self.address_group_util.update_address_group_spec(ag, address_group_object.data))
                except Exception as e:
                    self.exceptions.append(f"Failed to update Address Group '{ag['name']}': {e}")

            if not ags_to_update:
                self.logger.warning(f"No Address Groups to update in {self.data['pc_ip']!r}. Skipping...")
                return
            self.logger.info(f"Trigger batch update API for Address groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.address_group_util.batch_op.batch_update(entity_update_list=ags_to_update)
            
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Updation of Address Group in PC didn't happen in the"
                                           " prescribed timeframe")        

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.address_groups:
            return

        # Initial status
        self.results["Update_Address_groups"] = {}

        address_group_name_list = []

        for ag in self.address_groups:
            # Initial status
            self.results["Update_Address_groups"][ag.get("name")] = "CAN'T VERIFY"

            address_group_name_list = address_group_name_list or self.address_group_util.get_name_list()
            name = (ag["new_name"] if ag.get("new_name") else ag["name"])
            if name in address_group_name_list:
                self.results["Update_Address_groups"][ag["name"]] = "PASS"
            else:
                self.results["Update_Address_groups"][ag["name"]] = "FAIL"
