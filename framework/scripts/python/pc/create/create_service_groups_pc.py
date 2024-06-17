import time
from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.service_group import ServiceGroup
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateServiceGroups(Script):
    """
    Class that creates Service Groups
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.service_groups = self.data.get("service_groups")
        self.pc_session = self.data["pc_session"]
        super(CreateServiceGroups, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if not self.service_groups:
                self.logger.warning(f"No service_groups to create in {self.data['pc_ip']!r}. Skipping...")
                return

            service_group = ServiceGroup(self.pc_session)
            service_group_list = service_group.list(length=10000)
            service_group_name_list = [ag.get("service_group", {}).get("name")
                                       for ag in service_group_list if ag.get("service_group", {}).get("name")]
            sgs_to_create = []
            for sg in self.service_groups:
                if sg["name"] in service_group_name_list:
                    self.logger.warning(f"{sg['name']} already exists!")
                    continue
                try:
                    sgs_to_create.append(service_group.create_service_group_spec(sg))
                except Exception as e:
                    self.exceptions.append(f"Failed to create Security policy {sg['name']}: {e}")

            if not sgs_to_create:
                self.logger.warning(f"No service_groups to create in {self.data['pc_ip']!r}. Skipping...")
                return

            self.logger.info(f"Trigger batch create API for service groups in {self.data['pc_ip']!r}")
            service_group.batch_op.batch_create(request_payload_list=sgs_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.service_groups:
            return

        # Initial status
        self.results["Create_Service_groups"] = {}

        # There is no monitor option for creation. Hence, waiting for creation before verification
        time.sleep(5)
        service_group = ServiceGroup(self.pc_session)
        service_group_list = []
        service_group_name_list = []

        for sg in self.service_groups:
            # Initial status
            self.results["Create_Service_groups"][sg["name"]] = "CAN'T VERIFY"

            service_group_list = service_group_list or service_group.list(length=10000)
            service_group_name_list = service_group_name_list or [ag.get("service_group", {}).get("name")
                                                                  for ag in service_group_list if
                                                                  ag.get("service_group", {}).get("name")]
            if sg["name"] in service_group_name_list:
                self.results["Create_Service_groups"][sg["name"]] = "PASS"
            else:
                self.results["Create_Service_groups"][sg["name"]] = "FAIL"
