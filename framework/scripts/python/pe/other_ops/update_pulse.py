from typing import Dict
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.pulse import Pulse
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class UpdatePulsePe(ClusterScript):
    """
    Udpate Pulse
    """

    def __init__(self, data: Dict, **kwargs):
        super(UpdatePulsePe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def update_pulse(self, pe_session: RestAPIUtil, enable_pulse: bool, cluster_info):
        pulse = Pulse(session=pe_session)

        # get current status
        current_status = pulse.read().get("enable")

        if current_status == enable_pulse:
            self.logger.warning(f"Pulse is already '{enable_pulse}' in the cluster {cluster_info!r}")

        pulse.update_pulse(enable=enable_pulse)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"
        pe_session = cluster_details["pe_session"]

        if "enable_pulse" in cluster_details:
            try:
                self.update_pulse(pe_session, cluster_details.get("enable_pulse", False), cluster_info)
            except Exception as e:
                self.exceptions.append(f"Update_pulse failed for the cluster {cluster_info!r} with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        if "enable_pulse" not in cluster_details:
            return

        self.results["clusters"][cluster_ip] = {
            "Update_Pulse": "CAN'T VERIFY"
        }

        try:
            pe_session = cluster_details["pe_session"]

            if cluster_details.get("enable_pulse", None) is not None:
                # Check if Pulse is updated
                pulse = Pulse(session=pe_session)
                # get current status
                current_status = pulse.read().get("enable")
                if current_status == cluster_details.get("enable_pulse"):
                    self.results["clusters"][cluster_ip]["Update_Pulse"] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Update_Pulse"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for "
                             f"{cluster_ip}")
