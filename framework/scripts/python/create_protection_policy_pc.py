from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.cluster import Cluster as PcCluster
from scripts.python.helpers.v3.protection_rule import ProtectionRule
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateProtectionPolicy(Script):
    """
    Class that creates PP
    """
    def __init__(self, data: dict):
        self.task_uuid_list = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(CreateProtectionPolicy, self).__init__()

    def execute(self, **kwargs):
        try:
            protection_policy = ProtectionRule(self.pc_session)
            protection_policy_list = protection_policy.list()
            protection_policy_name_list = [pp.get("spec", {}).get("name")
                                           for pp in protection_policy_list if pp.get("spec", {}).get("name")]

            if not self.data.get("protection_rules"):
                logger.warning(f"Skipping creation of Protection policies in {self.data['pc_ip']}")
                return

            source_pc_cluster = PcCluster(self.pc_session)
            source_pc_cluster.get_pe_info_list()
            source_pe_clusters = {
                self.data["pc_ip"]: source_pc_cluster.name_uuid_map
            }

            if not self.data.get("remote_azs"):
                logger.warning(f"AZs are to be provided in {self.data['pc_ip']}")
                return

            remote_pe_clusters = {}
            for az, details in self.data["remote_azs"].items():
                remote_pc_username = details["username"]
                remote_pc_password = details["password"]
                remote_pc_cluster = PcCluster(
                    RestAPIUtil(az, user=remote_pc_username, pwd=remote_pc_password, port="9440", secured=True))
                remote_pc_cluster.get_pe_info_list()
                remote_pe_clusters[az] = remote_pc_cluster.name_uuid_map

            pp_list = []
            for pp in self.data["protection_rules"]:
                if pp['name'] in protection_policy_name_list:
                    logger.warning(f"{pp['name']} already exists in {self.data['pc_ip']}!")
                    continue

                try:
                    spec = protection_policy.get_payload(pp, source_pe_clusters, remote_pe_clusters)
                    pp_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to create Protection policy {pp['name']}: {e}")

            if not pp_list:
                logger.warning(f"Provided PPs are already created in {self.data['pc_ip']}")
                return

            logger.info(f"Batch create Protection policies in {self.data['pc_ip']}")
            self.task_uuid_list = protection_policy.batch_op.batch_create(request_payload_list=pp_list)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.task_uuid_list:
            app_response, status = PcTaskMonitor(self.pc_session,
                                                 task_uuid_list=self.task_uuid_list).monitor()

            if app_response:
                self.exceptions.append(f"Some tasks have failed. {app_response}")

            if not status:
                self.exceptions.append(
                    "Timed out. Creation of Protection policies in PC didn't happen in the prescribed timeframe")
