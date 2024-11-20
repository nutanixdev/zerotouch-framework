from typing import Dict
from framework.helpers.log_utils import get_logger
from ...helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from ...helpers.v3.cluster import Cluster as PcCluster
from ...helpers.v3.network import Network
from ...script import Script

logger = get_logger(__name__)


class DeleteSubnetsPc(Script):
    """
    Class that deletes subnets in PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.pe_clusters = self.data.get("clusters", {})
        super(DeleteSubnetsPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            network = Network(session=self.pc_session)
            subnets_to_delete = []

            for _, cluster_details in self.pe_clusters.items():
                for subnet_info in cluster_details.get("networks", []):
                    if subnet_info.get("uuid"):
                        subnets_to_delete.append(subnet_info["uuid"])
                    else:
                        # Filtering with name & use vlanid if it is passed in config
                        cluster_name = cluster_details["cluster_info"]["name"]
                        cluster_uuid = cluster_details["cluster_info"].get("uuid")
                        if not cluster_uuid:
                            pc_cluster = PcCluster(self.pc_session)
                            pc_cluster.get_pe_info_list()
                            cluster_uuid = pc_cluster.name_uuid_map.get(cluster_name)
                            if not cluster_uuid:
                                self.exceptions.append(f"Failed to delete subnets in {cluster_name}")
                                continue

                        filter_criteria = f"cluster_name=={cluster_name};name=={subnet_info['name']}"
                        if subnet_info.get("vlan_id"):
                            filter_criteria += f";vlan_id=={subnet_info['vlan_id']}"
                        subnets_response = network.list(filter=filter_criteria)
                        if len(subnets_response) < 0:
                            self.logger.warning(f"Skipping Subnet Deletion. Subnet {subnet_info['name']} "
                                                f"does not exists in the cluster {cluster_name}")
                        else:
                            try:
                                for response in subnets_response:
                                    subnets_to_delete.append(response["metadata"]["uuid"])
                                self.logger.debug(subnets_to_delete)
                            except Exception as e:
                                self.exceptions.append(f"Failed to delete subnet {subnet_info['name']} in {cluster_name}: {e}")

            if not subnets_to_delete:
                self.logger.warning(f"No subnets to delete in '{self.data['pc_ip']}'")
                return

            self.logger.info(f"Batch delete subnets in '{self.data['pc_ip']}'")
            self.task_uuid_list = network.batch_delete_network(subnets_to_delete)

            if self.task_uuid_list:
                pc_task_monitor = PcTaskMonitor(self.pc_session,
                                                task_uuid_list=self.task_uuid_list)
                pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 10
                pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 600
                app_response, status = pc_task_monitor.monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Deletion of subnets in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Initial status
        self.results["clusters"] = {}

        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                self.results["clusters"][cluster_ip] = {"Delete_subnets": {}}
                if not cluster_details.get("networks"):
                    continue

                network = Network(session=self.pc_session)
                for subnet_info in cluster_details.get("networks", []):
                    if subnet_info.get("uuid"):
                        uuid = subnet_info["uuid"]
                        self.results["clusters"][cluster_ip]["Delete_subnets"][uuid] = "CAN'T VERIFY"
                        try:
                            network.read(uuid=uuid)
                            self.results["clusters"][cluster_ip]["Delete_subnets"][uuid] = "FAIL"
                        except Exception as e:
                            # api will throw exception if the uuid is not present
                            self.logger.debug(e)
                            self.results["clusters"][cluster_ip]["Delete_subnets"][uuid] = "PASS"
                    else:
                        subnet_name = subnet_info['name']
                        self.results["clusters"][cluster_ip]["Delete_subnets"][subnet_name] = "CAN'T VERIFY"

                        cluster_name = cluster_details["cluster_info"]["name"]
                        filter_criteria = f"cluster_name=={cluster_name};name=={subnet_info['name']}"
                        if subnet_info.get("vlan_id"):
                            filter_criteria += f";vlan_id=={subnet_info['vlan_id']}"

                        subnets_response = network.list(filter=filter_criteria)
                        if len(subnets_response) > 0:
                            self.results["clusters"][cluster_ip]["Delete_subnets"][subnet_name] = "FAIL"
                        else:
                            self.results["clusters"][cluster_ip]["Delete_subnets"][subnet_name] = "PASS"
            except Exception as e:
                self.logger.debug(e)
                self.logger.info(
                    f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
