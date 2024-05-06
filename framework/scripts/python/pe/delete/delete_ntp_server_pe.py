from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.cluster import Cluster

logger = get_logger(__name__)


class DeleteNtpServersPe(ClusterScript):
    """
    Class that deletes NTP servers in PE
    """
    def __init__(self, data: Dict, **kwargs):
        super(DeleteNtpServersPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)
        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"
        
        try:
            if cluster_details.get("ntp_servers_list"):
                
                pe_cluster = Cluster(pe_session)
                self.logger.info(f"Deleting ntp servers in {cluster_info!r}")
                response = pe_cluster.delete_ntp_servers(cluster_details["ntp_servers_list"])
                if response.get("value"):
                    self.logger.info(f"Deleting ntp servers {cluster_details['ntp_servers_list']} successful"
                                     f" in {cluster_info!r}!")
                else:
                    raise Exception(f"Could not delete ntp servers {cluster_details['ntp_servers_list']}"
                                    f" in {cluster_info!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            if not cluster_details.get("ntp_servers_list"):
                return

            # Initial status
            self.results["clusters"][cluster_ip] = {"DeleteNtpServers": {}}

            # Use v1 with PE url
            pe_session = cluster_details["pe_session"]
            pe_cluster = Cluster(pe_session)
            current_ntp_servers_list = []

            for ntp_server in cluster_details["ntp_servers_list"]:
                # Initial status
                self.results["clusters"][cluster_ip]["DeleteNtpServers"][ntp_server] = "CAN'T VERIFY"

                current_ntp_servers_list = current_ntp_servers_list or pe_cluster.get_ntp_servers()
                if ntp_server not in current_ntp_servers_list:
                    self.results["clusters"][cluster_ip]["DeleteNtpServers"][ntp_server] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["DeleteNtpServers"][ntp_server] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
