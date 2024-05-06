from typing import Dict
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.cluster import Cluster
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class RebuildCapacityReservation(ClusterScript):
    """
    Class that enables/disables Rebuild Capacity Reservation
    """

    def __init__(self, data: Dict, **kwargs):
        super(RebuildCapacityReservation, self).__init__(data, **kwargs)
        self.logger = self.logger or logger
        self.cluster_size = None

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        if cluster_details.get("enable_rebuild_reservation") is None:
            self.logger.warning(f"Rebuild reservation is not passed in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                f" Skipping...'")
            return

        pe_session = cluster_details["pe_session"]
        cluster = PeCluster(pe_session)
        cluster.get_cluster_info()
        cluster_details["cluster_info"].update(cluster.cluster_info)
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        # Check if the cluster size is equal to or than 2, as rebuild is not supported for 1 and 2 node clusters.
        if cluster_details["cluster_info"]["num_nodes"] <= 2:
            self.logger.warning("Rebuild reservation feature can not be enabled for 1 and 2 node cluster "
                                f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'. Skipping...'")
            return

        # Check if enable_rebuild_reservation is already in required state
        if cluster_details["cluster_info"]["enable_rebuild_reservation"] == cluster_details["enable_rebuild_reservation"]:
            self.logger.warning(f"Enable Rebuild is already {cluster_details['enable_rebuild_reservation']} "
                                f"for '{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
            return

        try:
            self.logger.info(f"Updating Rebuild Reservation in {cluster_info!r}")
            rebuild_op = Cluster(session=pe_session)
            response = rebuild_op.update_rebuild_reservation(cluster_details.get("enable_rebuild_reservation"))
            if response.get("value"):
                self.logger.info(f"{type(self).__name__} successfully updated for the cluster {cluster_info!r}")
            else:
                self.exceptions.append(f"{type(self).__name__} failed to update for the cluster {cluster_info!r}")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            self.results["clusters"][cluster_ip] = {"Rebuild_state": "CAN'T VERIFY"}
            if cluster_details.get("enable_rebuild_reservation") is None:
                return

            if cluster_details['cluster_info']["num_nodes"] <= 2:
                self.results["clusters"][cluster_ip] = {"Rebuild_state": "Not Applicable for 1 and 2 node cluster"}
                return
            pe_session = cluster_details["pe_session"]
            rebuild_op = Cluster(session=pe_session)
            response = rebuild_op.read()
            if response["enableRebuildReservation"] == cluster_details["enable_rebuild_reservation"]:
                self.results["clusters"][cluster_ip] = {"Rebuild_state": "Pass"}
            else:
                self.results["clusters"][cluster_ip] = {"Rebuild_state": "Failed to update Rebuild Reservation"}

        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
