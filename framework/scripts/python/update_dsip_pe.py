from typing import Dict
from .helpers.v2.cluster import Cluster as PeCluster
from .cluster_script import ClusterScript
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class UpdateDsip(ClusterScript):
    """
    Update DSIP for the input PE clusters
    """
    def __init__(self, data: Dict, **kwargs):
        super(UpdateDsip, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        if not cluster_details.get("dsip"):
            self.logger.warning(f"DSIP is not passed in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                f" Skipping...'")
            return

        pe_session = cluster_details["pe_session"]
        cluster = PeCluster(pe_session)
        cluster.get_cluster_info()
        cluster_details["cluster_info"].update(cluster.cluster_info)
        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"

        current_dsip = cluster_details.get("cluster_info", {}).get("cluster_external_data_services_ipaddress")
        if current_dsip:
            self.logger.warning(f"Data services IP is already set to {current_dsip} in {cluster_info}")
            return

        try:
            self.logger.info(f"Updating DSIP in {cluster_info}")
            response = cluster.update_dsip(cluster_details["dsip"])

            if response["value"]:
                self.logger.info(f"Updated cluster DSIP to {cluster_details['dsip']} in {cluster_info}")
            else:
                self.exceptions.append(f"Failed to update cluster DSIP in {cluster_info}")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}")
            return

    def verify(self):
        # Check if DSIP was updated
        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                if not cluster_details.get("dsip"):
                    continue

                self.results["clusters"][cluster_ip] = {
                    "Update_DSIP": "CAN'T VERIFY"
                }

                pe_session = cluster_details["pe_session"]
                cluster = PeCluster(pe_session)
                cluster.get_cluster_info()
                cluster_details["cluster_info"].update(cluster.cluster_info)

                dsip = cluster_details.get("cluster_info", {}).get("cluster_external_data_services_ipaddress")
                if dsip:
                    self.results["clusters"][cluster_ip]["Update_DSIP"] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Update_DSIP"] = "FAIL"
            except Exception as e:
                self.logger.debug(e)
                self.logger.info(
                    f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
