import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class CreateAddressGroups(PcScript):
    """
    Class that creates Address Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(CreateAddressGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.address_group_util = self.import_helpers_with_version_handling("AddressGroup")

    def execute(self):
        try:
            address_group_name_list = self.address_group_util.get_name_list()
            if not self.address_groups:
                self.logger.warning(f"No Address Groups to create in {self.data['pc_ip']!r}. Skipping...")
                return

            ags_to_create = []
            for ag in self.address_groups:
                if ag["name"] in address_group_name_list:
                    self.logger.warning(f"'{ag['name']}' Address Group already exists in {self.data['pc_ip']!r}!")
                    continue
                try:
                    self.logger.info(f"Creating Address Group '{ag['name']}' in {self.data['pc_ip']!r}")
                    ags_to_create.append(self.address_group_util.create_address_group_spec(ag))
                except Exception as e:
                    self.exceptions.append(f"Failed to create address_group '{ag['name']}': {e}")

            if not ags_to_create:
                self.logger.warning(f"No Address Groups to create in {self.data['pc_ip']!r}. Skipping...")
                return
            self.logger.info(f"Trigger batch create API for Address groups in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.address_group_util.batch_op.batch_create(request_payload_list=ags_to_create)
            
            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of Address Groups in PC didn't happen in the"
                                           " prescribed timeframe")        
    
            
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.address_groups:
            return

        # Initial status
        self.results["Create_Address_groups"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)
        address_group_name_list = []

        for ag in self.address_groups:
            # Initial status
            self.results["Create_Address_groups"][ag.get("name")] = "CAN'T VERIFY"

            address_group_name_list = address_group_name_list or self.address_group_util.get_name_list()

            if ag["name"] in address_group_name_list:
                self.results["Create_Address_groups"][ag["name"]] = "PASS"
            else:
                self.results["Create_Address_groups"][ag["name"]] = "FAIL"
