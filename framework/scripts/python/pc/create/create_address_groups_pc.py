import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.address_group import AddressGroup
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateAddressGroups(Script):
    """
    Class that creates Address Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.address_groups = self.data.get("address_groups")
        self.pc_session = self.data["pc_session"]
        super(CreateAddressGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            address_group = AddressGroup(self.pc_session)
            address_group_list = address_group.list()
            address_group_name_list = [ag.get("address_group", {}).get("name")
                                       for ag in address_group_list if ag.get("address_group", {}).get("name")]

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
                    ags_to_create.append(address_group.create_address_group_spec(ag))
                except Exception as e:
                    self.exceptions.append(f"Failed to create address_group '{ag['name']}': {e}")

            if not ags_to_create:
                self.logger.warning(f"No Address Groups to create in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch create API for Address groups in {self.data['pc_ip']!r}")
            address_group.batch_op.batch_create(request_payload_list=ags_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.address_groups:
            return

        # Initial status
        self.results["Create_Address_groups"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)
        address_group = AddressGroup(self.pc_session)
        address_group_list = []
        address_group_name_list = []

        for ag in self.address_groups:
            # Initial status
            self.results["Create_Address_groups"][ag.get("name")] = "CAN'T VERIFY"

            address_group_list = address_group_list or address_group.list()
            address_group_name_list = address_group_name_list or [ag.get("address_group", {}).get("name")
                                                                  for ag in address_group_list if
                                                                  ag.get("address_group", {}).get("name")]
            if ag["name"] in address_group_name_list:
                self.results["Create_Address_groups"][ag["name"]] = "PASS"
            else:
                self.results["Create_Address_groups"][ag["name"]] = "FAIL"
