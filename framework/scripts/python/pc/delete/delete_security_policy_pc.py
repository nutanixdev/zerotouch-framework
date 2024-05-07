from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.security_rule import SecurityPolicy
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteNetworkSecurityPolicy(Script):
    """
    Class that deletes Security policies
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        super(DeleteNetworkSecurityPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            security_policy = SecurityPolicy(self.pc_session)
            security_policy_list = security_policy.list(length=10000)

            security_policy_name_uuid_dict = {
                sp.get("spec").get("name"): sp.get("metadata").get("uuid")
                for sp in security_policy_list
                if sp.get("spec", {}).get("name")
            }

            if not self.security_policies:
                self.logger.warning(
                    f"No security_policies to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            sps_to_delete_uuids = []
            for sg in self.security_policies:
                if sg['name'] not in security_policy_name_uuid_dict.keys():
                    self.logger.warning(
                        f"{sg['name']} Security Policy doesn't exist in {self.data['pc_ip']!r}!"
                    )
                    continue
                try:
                    sps_to_delete_uuids.append(security_policy_name_uuid_dict[sg['name']])
                except Exception as e:
                    self.exceptions.append(f"Failed to delete Security policy {sg['name']}: {e}")

            if not sps_to_delete_uuids:
                self.logger.warning(
                    f"No security_policies to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            self.logger.info(f"Trigger batch delete API for Security Policies in {self.data['pc_ip']!r}")
            self.task_uuid_list = security_policy.batch_op.batch_delete(entity_list=sps_to_delete_uuids)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session,
                    task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Security policies in PC didn't happen in the"
                        " prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.security_policies:
            return

        # Initial status
        self.results["Delete_Security_policies"] = {}
        security_policy = SecurityPolicy(self.pc_session)
        security_policy_list = []
        security_policy_name_list = []

        for sec_pol in self.security_policies:
            # Initial status
            self.results["Delete_Security_policies"][sec_pol['name']] = "CAN'T VERIFY"

            security_policy_list = security_policy_list or security_policy.list(length=10000)
            security_policy_name_list = security_policy_name_list or [
                sp.get("spec").get("name") for
                sp in security_policy_list if
                sp.get("spec", {}).get("name")
            ]
            if sec_pol["name"] not in security_policy_name_list:
                self.results["Delete_Security_policies"][sec_pol['name']] = "PASS"
            else:
                self.results["Delete_Security_policies"][sec_pol['name']] = "FAIL"
