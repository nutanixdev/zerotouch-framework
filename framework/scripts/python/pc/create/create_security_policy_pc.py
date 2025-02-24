from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript


logger = get_logger(__name__)


class CreateNetworkSecurityPolicy(PcScript):
    """
    Class that creates Security policies
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(CreateNetworkSecurityPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.security_policy_util = self.import_helpers_with_version_handling("SecurityPolicy")

    def execute(self):
        try:
            if not self.security_policies:
                self.logger.warning(f"No security_policies to create in {self.data['pc_ip']!r}. Skipping...")
                return

            security_policy_name_list = self.security_policy_util.get_name_list()
            sps_to_create = []
            for sg in self.security_policies:
                if sg["name"] in security_policy_name_list:
                    self.logger.warning(f" Security Policy with name {sg['name']} already exists in {self.data['pc_ip']!r}!")
                    continue
                try:
                    sps_to_create.append(self.security_policy_util.create_security_policy_spec(sg))
                except Exception as e:
                    self.exceptions.append(f"Failed to create Security policy {sg['name']}: {e}")

            if not sps_to_create:
                self.logger.warning(f"No security_policies to create in {self.data['pc_ip']!r}. Skipping...")
                return
            self.logger.info(f"Trigger batch create API for Security Policies in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.security_policy_util.batch_op.batch_create(request_payload_list=sps_to_create)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list,
                    task_op=self.import_helpers_with_version_handling('Task')).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of Security policies in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.security_policies:
            return

        # Initial status
        self.results["Create_Security_policies"] = {}
        security_policy_name_list = []

        for sg in self.security_policies:
            self.results["Create_Security_policies"][sg['name']] = "CAN'T VERIFY"

            security_policy_name_list = security_policy_name_list or self.security_policy_util.get_name_list()

            if sg["name"] in security_policy_name_list:
                self.results["Create_Security_policies"][sg['name']] = "PASS"
            else:
                self.results["Create_Security_policies"][sg['name']] = "FAIL"
