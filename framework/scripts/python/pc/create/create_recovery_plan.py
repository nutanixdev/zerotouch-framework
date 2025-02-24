from typing import Dict

from framework.helpers.helper_functions import read_creds
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.cluster import Cluster as PcCluster
from framework.scripts.python.helpers.v3.recovery_plan import RecoveryPlan
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class CreateRecoveryPlan(Script):
    """
    Class that creates RP
    """

    def __init__(self, data: Dict, **kwargs):
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
                self.logger.warning(f"Skipping creation of Recovery plans in {self.data['pc_ip']!r}")
                return

            source_pc_cluster = PcCluster(self.pc_session)
            source_pc_cluster.get_pe_info_list()
            source_pe_clusters = {
                self.data["pc_ip"]: source_pc_cluster.name_uuid_map
            }

            # if not self.data.get("remote_azs"):
            #     self.logger.warning(f"AZs are to be provided in {self.data['pc_ip']!r}")
            #     return

            remote_pe_clusters = {}
            if self.data.get("remote_azs"):
                for az, details in self.data["remote_azs"].items():
                    remote_pc_credential = details.get("pc_credential")
                    # get credentials from the payload
                    try:
                        remote_pc_username, remote_pc_password = read_creds(data=self.data,
                                                                            credential=remote_pc_credential)
                    except Exception as e:
                        self.exceptions.append(e)
                        continue

                    remote_pc_cluster = PcCluster(
                        RestAPIUtil(az, user=remote_pc_username, pwd=remote_pc_password, port="9440", secured=True))
                    remote_pc_cluster.get_pe_info_list()
                    remote_pe_clusters[az] = remote_pc_cluster.name_uuid_map

            # destination cluster can be from local az as well
            remote_pe_clusters.update(source_pe_clusters)

            rp_list = []
            for rp in self.data["recovery_plans"]:
                if rp['name'] in recovery_plan_name_list:
                    self.logger.warning(f"{rp['name']} already exists in {self.data['pc_ip']!r}!")
                    continue

                try:
                    spec = recovery_plan.get_payload(rp, source_pe_clusters, remote_pe_clusters)
                    rp_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to create Recovery plan {rp['name']}: {e}")

            if not rp_list:
                self.logger.warning(f"No recovery plans to create in {self.data['pc_ip']!r}")
                return

            logger.info(f"Trigger batch create API for Recovery plans in {self.data['pc_ip']!r}")
            self.task_uuid_list = recovery_plan.batch_op.batch_create(request_payload_list=rp_list)

            if self.task_uuid_list:
                app_response, status = TaskMonitor(self.pc_session,
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
