from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.scripts.python.helpers.v3.recovery_plan import RecoveryPlan
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteRecoveryPlan(Script):
    """
    Class that deletes Recovery Plan
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(DeleteRecoveryPlan, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            recovery_plan = RecoveryPlan(self.pc_session)
            recovery_plan_list = recovery_plan.list()
            recovery_plan_name_uuid_map = {
                rp.get("spec", {}).get("name"): rp.get("metadata", {}).get("uuid")
                for rp in recovery_plan_list
                if rp.get("spec", {}).get("name")
            }

            if not self.data.get("recovery_plans"):
                self.logger.warning(
                    f"Skipping deletion of Recovery plans in {self.data['pc_ip']}"
                )
                return

            rp_list = []
            for rp in self.data["recovery_plans"]:
                if rp["name"] not in recovery_plan_name_uuid_map.keys():
                    self.logger.warning(
                        f"{rp['name']} doesn't exist in {self.data['pc_ip']}!"
                    )
                    continue

                rp_list.append(recovery_plan_name_uuid_map[rp["name"]])

            if not rp_list:
                self.logger.warning(
                    f"Provided Recovery Plans are not present in {self.data['pc_ip']}"
                )
                return

            logger.info(f"Trigger batch delete API for Recovery plans in {self.data['pc_ip']!r}")
            self.task_uuid_list = recovery_plan.batch_op.batch_delete(entity_list=rp_list)

            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(
                    self.pc_session, task_uuid_list=self.task_uuid_list
                ).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of Recovery plans in PC didn't happen in the prescribed timeframe"
                    )
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("recovery_plans"):
            return

        # Initial status
        self.results["Delete_Recovery_plans"] = {}

        recovery_plan = RecoveryPlan(self.pc_session)
        recovery_plan_list = []
        recovery_plan_name_list = []
        for rp in self.data["recovery_plans"]:
            # Initial status
            self.results["Delete_Recovery_plans"][rp["name"]] = "CAN'T VERIFY"

            recovery_plan_list = recovery_plan_list or recovery_plan.list()
            recovery_plan_name_list = recovery_plan_name_list or [
                rp.get("spec", {}).get("name")
                for rp in recovery_plan_list
                if rp.get("spec", {}).get("name")
            ]
            if rp["name"] not in recovery_plan_name_list:
                self.results["Delete_Recovery_plans"][rp["name"]] = "PASS"
            else:
                self.results["Delete_Recovery_plans"][rp["name"]] = "FAIL"
