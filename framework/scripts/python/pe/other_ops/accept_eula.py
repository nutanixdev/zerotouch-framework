from typing import Dict
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.eula import Eula
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class AcceptEulaPe(ClusterScript):
    """
    Accept Eula
    """
    def __init__(self, data: Dict, **kwargs):
        super(AcceptEulaPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def accept_eula(self, pe_session: RestAPIUtil, data: Dict, cluster_info):
        eula = Eula(pe_session)

        if eula.is_eula_accepted():
            self.logger.warning(f"Eula is already accepted for the cluster {cluster_info!r}")
            return
        response = eula.accept_eula(**data)

        if response.get("value"):
            self.logger.info(f"Accepted End-User License Agreement in {cluster_info!r}")
        else:
            raise Exception(f"Could not Accept End-User License Agreement in {cluster_info!r}. Error: {response}")

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        if "eula" in cluster_details:
            try:
                self.accept_eula(pe_session, cluster_details.get("eula"), cluster_info)
            except Exception as e:
                self.exceptions.append(f"Accept_eula failed for the cluster {cluster_info!r} with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        if "eula" not in cluster_details:
            return

        self.results["clusters"][cluster_ip] = {
            "Accept_Eula": "CAN'T VERIFY"
        }

        try:
            pe_session = cluster_details["pe_session"]

            # Check if Eula is accepted
            eula = Eula(pe_session)

            if eula.is_eula_accepted():
                self.results["clusters"][cluster_ip]["Accept_Eula"] = "PASS"
            else:
                self.results["clusters"][cluster_ip]["Accept_Eula"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for "
                             f"{cluster_ip}")
