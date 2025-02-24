from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.pc.pc_script import PcScript

logger = get_logger(__name__)


class DeleteNetworkSecurityPolicy(PcScript):
    """
    Class that deletes Security policies
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.security_policies = self.data.get("security_policies")
        self.pc_session = self.data["pc_session"]
        self.v4_api_util = self.data["v4_api_util"]
        super(DeleteNetworkSecurityPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger
        self.security_policy_util = self.import_helpers_with_version_handling("SecurityPolicy")

    def execute(self):
        try:
            security_policy_name_uuid_dict = self.security_policy_util.get_name_uuid_dict()

            if not self.security_policies:
                self.logger.warning(
                    f"No security_policies provided to delete in {self.data['pc_ip']!r}"
                )
                return

            sps_to_delete = []
            for sg in self.security_policies:
                if sg['name'] not in security_policy_name_uuid_dict.keys():
                    self.logger.warning(
                        f"{sg['name']} Security Policy doesn't exist in {self.data['pc_ip']!r}!"
                    )
                    continue
                try:
                    sps_to_delete.append(
                        self.security_policy_util.delete_security_policy_spec(
                            security_policy_name_uuid_dict[sg['name']]
                            )
                        )
                except Exception as e:
                    self.exceptions.append(f"Failed to delete Security policy {sg['name']}: {e}")

            if not sps_to_delete:
                self.logger.warning(
                    f"No security_policies to delete in {self.data['pc_ip']!r}. Skipping..."
                )
                return

            self.logger.info(f"Trigger batch delete API for Security Policies in {self.data['pc_ip']!r}")
            self.task_uuid_list = self.security_policy_util.batch_op.batch_delete(entity_list=sps_to_delete)

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
                        "Timed out. Deletion of Security policies in PC didn't happen in the"
                        " prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        if not self.security_policies:
            return

        # Initial status
        self.results["Delete_Security_policies"] = {}
        security_policy_name_list = []

        for sec_pol in self.security_policies:
            security_policy_name_list = security_policy_name_list or self.security_policy_util.get_name_list()
            # Initial status
            self.results["Delete_Security_policies"][sec_pol['name']] = "CAN'T VERIFY"

            if sec_pol["name"] not in security_policy_name_list:
                self.results["Delete_Security_policies"][sec_pol['name']] = "PASS"
            else:
                self.results["Delete_Security_policies"][sec_pol['name']] = "FAIL"
