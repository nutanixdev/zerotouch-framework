from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.scripts.python.helpers.v3.cluster import Cluster as PcCluster
from framework.scripts.python.helpers.v3.protection_rule import ProtectionRule
from framework.scripts.python.script import Script
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class CreateProtectionPolicy(Script):
    """
    Class that creates PP
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(CreateProtectionPolicy, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if not self.data.get("protection_rules"):
                self.logger.warning(f"Skipping creation of Protection policies in {self.data['pc_ip']!r}")
                return

            protection_policy = ProtectionRule(self.pc_session)
            protection_policy_list = protection_policy.list()
            protection_policy_name_list = [pp.get("spec", {}).get("name")
                                           for pp in protection_policy_list if pp.get("spec", {}).get("name")]

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

            pp_list = []
            for pp in self.data["protection_rules"]:
                if pp['name'] in protection_policy_name_list:
                    self.logger.warning(f"{pp['name']} Protection Policy already exists in {self.data['pc_ip']!r}!")
                    continue

                try:
                    spec = protection_policy.get_payload(pp, source_pe_clusters, remote_pe_clusters)
                    pp_list.append(spec)
                except Exception as e:
                    self.exceptions.append(f"Failed to create Protection policy {pp['name']}: {e}")

            if not pp_list:
                self.logger.warning(f"No Protection policies to create in {self.data['pc_ip']!r}")
                return

            logger.info(f"Trigger batch create API for Protection policies in {self.data['pc_ip']!r}")
            self.task_uuid_list = protection_policy.batch_op.batch_create(request_payload_list=pp_list)

            # Monitor the tasks
            if self.task_uuid_list:
                app_response, status = TaskMonitor(self.pc_session,
                                                   task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Creation of Protection policies in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("protection_rules"):
            return

        # Initial status
        self.results["Create_Protection_policies"] = {}

        protection_policy = ProtectionRule(self.pc_session)
        protection_policy_list = []
        protection_policy_name_list = []

        for pp in self.data["protection_rules"]:
            # Initial status
            self.results["Create_Protection_policies"][pp['name']] = "CAN'T VERIFY"

            protection_policy_list = protection_policy_list or protection_policy.list()
            protection_policy_name_list = protection_policy_name_list or [pp.get("spec", {}).get("name")
                                                                          for pp in protection_policy_list if
                                                                          pp.get("spec", {}).get("name")]
            if pp['name'] in protection_policy_name_list:
                self.results["Create_Protection_policies"][pp['name']] = "PASS"
            else:
                self.results["Create_Protection_policies"][pp['name']] = "FAIL"
