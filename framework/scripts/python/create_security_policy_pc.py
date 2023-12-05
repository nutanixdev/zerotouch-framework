from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from .helpers.v3.security_rule import SecurityPolicy
from .script import Script

logger = get_logger(__name__)


class CreateNetworkSecurityPolicy(Script):
    """
    Class that creates Security policies
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        super(CreateNetworkSecurityPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            security_policy = SecurityPolicy(self.pc_session)
            security_policy_list = security_policy.list(length=10000)
            security_policy_name_list = [sp.get("spec").get("name")
                                         for sp in security_policy_list if sp.get("spec", {}).get("name")]

            if not self.security_policies:
                self.logger.warning(f"No security_policies to create in '{self.data['pc_ip']}'. Skipping...")
                return

            sps_to_create = []
            for sg in self.security_policies:
                if sg["name"] in security_policy_name_list:
                    self.logger.warning(f"{sg['name']} Security Policy already exists in '{self.data['pc_ip']}'!")
                    continue
                try:
                    sps_to_create.append(security_policy.create_security_policy_spec(sg))
                except Exception as e:
                    self.exceptions.append(f"Failed to create Security policy {sg['name']}: {e}")

            if not sps_to_create:
                self.logger.warning(f"No security_policies to create in '{self.data['pc_ip']}'. Skipping...")
                return

            self.logger.info(f"Batch create Security Policies in '{self.data['pc_ip']}'")
            self.task_uuid_list = security_policy.batch_op.batch_create(request_payload_list=sps_to_create)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append("Timed out. Creation of Security policies in PC didn't happen in the"
                                           " prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.security_policies:
            return

        # Initial status
        self.results["Create_Security_policies"] = {}
        security_policy = SecurityPolicy(self.pc_session)
        security_policy_list = []
        security_policy_name_list = []

        for sg in self.security_policies:
            # Initial status
            self.results["Create_Security_policies"][sg['name']] = "CAN'T VERIFY"

            security_policy_list = security_policy_list or security_policy.list(length=10000)
            security_policy_name_list = security_policy_name_list or [sp.get("spec").get("name")
                                                                      for sp in security_policy_list if
                                                                      sp.get("spec", {}).get("name")]
            if sg["name"] in security_policy_name_list:
                self.results["Create_Security_policies"][sg['name']] = "PASS"
            else:
                self.results["Create_Security_policies"][sg['name']] = "FAIL"
