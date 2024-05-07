from typing import Dict
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v0_8.ha import HA
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor as TaskMonitor
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class HaReservation(ClusterScript):
    """
    Class that enables/disables HA reservation
    """

    def __init__(self, data: Dict, **kwargs):
        super(HaReservation, self).__init__(data, **kwargs)
        self.logger = self.logger or logger
        self.cluster_size = None

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        if not cluster_details.get("ha_reservation"):
            self.logger.warning(f"HA reservation is not passed in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                f" Skipping...'")
            return

        pe_session = cluster_details["pe_session"]
        cluster = PeCluster(pe_session)
        cluster.get_cluster_info()
        cluster_details["cluster_info"].update(cluster.cluster_info)
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        if cluster_details['cluster_info']["num_nodes"] == 1:
            self.logger.warning(f"HA reservation is not supported for single node cluster '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                                f" Skipping...'")
            return

        try:
            ha_op = HA(session=pe_session)
            response = ha_op.read()
            if response["numHostFailuresToTolerate"] == cluster_details["ha_reservation"].get("num_host_failure_to_tolerate", 1):
                self.logger.warning(f"HA is already enabled in {cluster_info!r} with numHostFailuresToTolerate {response['numHostFailuresToTolerate']}")
                return
            try:
                self.logger.info(f"Updating HA Reservation in {cluster_info!r}")
                response = ha_op.update_ha_reservation(**cluster_details.get("ha_reservation"))
                if response.get("taskUuid"):
                    app_response, status = TaskMonitor(pe_session,
                                                       task_uuid_list=[response["taskUuid"]]).monitor()
                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append("Timed out. OVA upload didn't happen in the prescribed timeframe")
            except Exception as e:
                self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                       f"{cluster_info!r} with the error: {e}")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            self.results["clusters"][cluster_ip] = {"HA_state": "CAN'T VERIFY"}
            if not cluster_details.get("ha_reservation"):
                return

            pe_session = cluster_details["pe_session"]
            if cluster_details['cluster_info']["num_nodes"] == 1:
                self.results["clusters"][cluster_ip] = {"HA_state": "Not Applicable for single node cluster"}
                return

            ha_op = HA(session=pe_session)
            response = ha_op.read()
            if response["numHostFailuresToTolerate"] == cluster_details["ha_reservation"].get("num_host_failure_to_tolerate", 1):
                self.results["clusters"][cluster_ip] = {"HA_state": f"Pass. Number of Host Failures To Tolerate is {response['numHostFailuresToTolerate']}"}
            else:
                self.results["clusters"][cluster_ip] = {"HA_state": "Failed to update HA Reservation"}

        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
