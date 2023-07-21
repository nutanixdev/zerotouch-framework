from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.cluster import Cluster as PcCluster
from scripts.python.helpers.v3.recovery_plan import RecoveryPlan
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateRecoveryPlan(Script):
    """
    Class that creates RP
    """

    def __init__(self, data: dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(CreateRecoveryPlan, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            recovery_plan = RecoveryPlan(self.pc_session)
            recovery_plan_list = recovery_plan.list()
            recovery_plan_name_list = [rp.get("spec", {}).get("name")
                                       for rp in recovery_plan_list if rp.get("spec", {}).get("name")]

            if not self.data.get("recovery_plans"):
                self.logger.warning(f"Skipping creation of Recovery plans in {self.data['pc_ip']}")
                return

            source_pc_cluster = PcCluster(self.pc_session)
            source_pc_cluster.get_pe_info_list()
            source_pe_clusters = {
                self.data["pc_ip"]: source_pc_cluster.name_uuid_map
            }

            if not self.data.get("remote_azs"):
                self.logger.warning(f"AZs are to be provided in {self.data['pc_ip']}")
                return

            rp_list = []
            for rp in self.data["recovery_plans"]:
                if rp['name'] in recovery_plan_name_list:
                    self.logger.warning(f"{rp['name']} already exists in {self.data['pc_ip']}!")
                    continue

                try:
                    spec = recovery_plan.get_payload(rp, source_pe_clusters)
                    rp_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to create Recovery plan {rp['name']}: {e}")

            if not rp_list:
                self.logger.warning(f"Provided RPs are already created in {self.data['pc_ip']}")
                return

            logger.info(f"Batch create Recovery plans in '{self.data['pc_ip']}'")
            self.task_uuid_list = recovery_plan.batch_op.batch_create(request_payload_list=rp_list)

            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Creation of Recovery plans in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("recovery_plans"):
            return

        # Initial status
        self.results["Create_Recovery_plans"] = {}

        recovery_plan = RecoveryPlan(self.pc_session)
        recovery_plan_list = []
        recovery_plan_name_list = []
        for rp in self.data["recovery_plans"]:
            # Initial status
            self.results["Create_Recovery_plans"][rp['name']] = "CAN'T VERIFY"

            recovery_plan_list = recovery_plan_list or recovery_plan.list()
            recovery_plan_name_list = recovery_plan_name_list or [rp.get("spec", {}).get("name")
                                                                  for rp in recovery_plan_list if
                                                                  rp.get("spec", {}).get("name")]
            if rp['name'] in recovery_plan_name_list:
                self.results["Create_Recovery_plans"][rp['name']] = "PASS"
            else:
                self.results["Create_Recovery_plans"][rp['name']] = "FAIL"
