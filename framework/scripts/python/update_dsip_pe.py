from scripts.python.helpers.v2.cluster import Cluster as PeCluster
from scripts.python.cluster_script import ClusterScript
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class UpdateDsip(ClusterScript):
    """
    Update DSIP for the input PE clusters
    """

    def __init__(self, data: dict, **kwargs):
        super(UpdateDsip, self).__init__(data, **kwargs)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        if not cluster_details.get("dsip"):
            logger.warning(f"DSIP is not passed in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                           f" Skipping...'")
            return

        pe_session = cluster_details["pe_session"]
        cluster = PeCluster(pe_session)

        current_dsip = cluster_details.get("cluster_info", {}).get("cluster_external_data_services_ipaddress")
        if current_dsip:
            logger.warning(f"Data services IP is already set to {current_dsip} in "
                           f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
            return

        try:
            response = cluster.update_dsip(cluster_details["dsip"])

            if response["value"]:
                logger.info(f"Updated cluster DSIP to {cluster_details['dsip']} in "
                            f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
            else:
                self.exceptions.append(f"Failed to update cluster DSIP in "
                                       f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
        except Exception as e:
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}")
            return

    def verify(self):
        # todo is there a way to verify these
        # do we need to verify these?
        pass
