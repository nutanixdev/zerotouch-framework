from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.cluster import Cluster

logger = get_logger(__name__)


class AddNameServersPe(ClusterScript):
    """
    Class that adds nameservers in PE
    """
    def __init__(self, data: Dict, **kwargs):
        super(AddNameServersPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("name_servers_list"):

                pe_cluster = Cluster(pe_session)
                self.logger.info(f"Adding name servers in {cluster_info!r}")
                response = pe_cluster.add_name_servers(cluster_details["name_servers_list"])
                if response.get("value"):
                    self.logger.info(f"Adding name servers {cluster_details['name_servers_list']} successful"
                                     f" in {cluster_info!r}!")
                else:
                    raise Exception(f"Could not add name servers {cluster_details['name_servers_list']}"
                                    f" in {cluster_info!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            if not cluster_details.get("name_servers_list"):
                return

            # Initial status
            self.results["clusters"][cluster_ip] = {"NameServers": {}}

            # Use v1 with PE url
            pe_session = cluster_details["pe_session"]
            pe_cluster = Cluster(pe_session)
            current_name_servers_list = []

            for name_server in cluster_details["name_servers_list"]:
                # Initial status
                self.results["clusters"][cluster_ip]["NameServers"][name_server] = "CAN'T VERIFY"

                current_name_servers_list = current_name_servers_list or pe_cluster.get_name_servers()
                if name_server in current_name_servers_list:
                    self.results["clusters"][cluster_ip]["NameServers"][name_server] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["NameServers"][name_server] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
