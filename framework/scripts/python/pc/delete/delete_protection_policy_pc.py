from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.protection_rule import ProtectionRule
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteProtectionPolicy(Script):
    """
    Class that deletes Protection Policy
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(DeleteProtectionPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            protection_policy = ProtectionRule(self.pc_session)
            protection_policy_list = protection_policy.list()
            protection_policy_name_uuid_map = {
                pp.get("spec", {}).get("name"): pp.get("metadata", {}).get("uuid")
                for pp in protection_policy_list if pp.get("spec", {}).get("name")
            }

            if not self.data.get("protection_rules"):
                self.logger.warning(
                    f"Skipping deletion of Protection policies in {self.data['pc_ip']!r}"
                )
                return

            pp_uuid_list = []
            for pp in self.data["protection_rules"]:
                if pp['name'] not in protection_policy_name_uuid_map.keys():
                    self.logger.warning(
                        f"{pp['name']} Protection Policy doesn't exist in {self.data['pc_ip']!r}!"
                    )
                    continue
                
                pp_uuid_list.append(protection_policy_name_uuid_map[pp['name']])

            if not pp_uuid_list:
                self.logger.warning(f"No protection policies to delete in {self.data['pc_ip']!r}")
                return

            logger.info(f"Trigger batch delete API for Protection policies in {self.data['pc_ip']!r}")
            self.task_uuid_list = protection_policy.batch_op.batch_delete(entity_list=pp_uuid_list)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session, task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Protection policies in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("protection_rules"):
            return

        # Initial status
        self.results["Delete_Protection_policies"] = {}

        protection_policy = ProtectionRule(self.pc_session)
        protection_policy_list = []
        protection_policy_name_list = []

        for pp in self.data["protection_rules"]:
            # Initial status
            self.results["Delete_Protection_policies"][pp['name']] = "CAN'T VERIFY"

            protection_policy_list = protection_policy_list or protection_policy.list()
            protection_policy_name_list = protection_policy_name_list or [
                pp.get("spec", {}).get("name")
                for pp in protection_policy_list
                if pp.get("spec", {}).get("name")
            ]
            if pp['name'] not in protection_policy_name_list:
                self.results["Delete_Protection_policies"][pp['name']] = "PASS"
            else:
                self.results["Delete_Protection_policies"][pp['name']] = "FAIL"
