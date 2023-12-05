import time
from typing import Dict
from .cluster_script import ClusterScript
from framework.helpers.rest_utils import RestAPIUtil
from .helpers.v1.utils_manager import UtilsManager
from .helpers.v1.eula import Eula
from .helpers.v1.pulse import Pulse
from .helpers.v2.cluster import Cluster as PeCluster
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class InitialClusterConfig(ClusterScript):
    """
    Change default PE password
    Accept Eula
    Enable Pulse
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        super(InitialClusterConfig, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def change_default_password(self, pe_session: RestAPIUtil, new_pe_password: str, cluster_info):
        default_system_password = UtilsManager(pe_session)
        response = default_system_password.change_default_system_password(new_pe_password)

        if response["value"]:
            self.logger.info(f"Default System password updated with new password in {cluster_info}")
        else:
            raise Exception(f"Could not change the PE password in {cluster_info}. Error: {response}")
        # Waiting for password sync
        time.sleep(30)

    def accept_eula(self, pe_session: RestAPIUtil, data: Dict, cluster_info):
        eula = Eula(pe_session)

        if eula.is_eula_accepted():
            self.logger.warning(f"Eula is already accepted for the cluster {cluster_info}")
            return
        response = eula.accept_eula(**data)

        if response["value"]:
            self.logger.info(f"Accepted End-User License Agreement in {cluster_info}")
        else:
            raise Exception(f"Could not Accept End-User License Agreement in {cluster_info}. Error: {response}")

    def update_pulse(self, pe_session: RestAPIUtil, enable_pulse: bool, cluster_info):
        pulse = Pulse(session=pe_session)

        # get current status
        current_status = pulse.read().get("enable")

        if current_status == enable_pulse:
            self.logger.warning(f"Pulse is already '{enable_pulse}' in the cluster {cluster_info}")

        pulse.update_pulse(enable=enable_pulse)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        new_pe_password = cluster_details.get('admin_pe_password') or cluster_details.get("pe_password")

        pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                 pwd=new_pe_password,
                                 port="9440", secured=True)

        if new_pe_password == self.DEFAULT_SYSTEM_PASSWORD:
            self.logger.error(f"New Password specified is same as default password for the cluster ...")
            return

        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"

        default_pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                         pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                         port="9440", secured=True)
        try:
            self.change_default_password(default_pe_session, new_pe_password, cluster_info)
        except Exception as e:
            self.exceptions.append(f"Change_default_password failed for the cluster {cluster_info} with the error: {e}")
        try:
            self.accept_eula(pe_session, cluster_details.get("eula"), cluster_info)
        except Exception as e:
            self.exceptions.append(f"Accept_eula failed for the cluster {cluster_info} with the error: {e}")
        try:
            self.update_pulse(pe_session, cluster_details.get("enable_pulse", False), cluster_info)
        except Exception as e:
            self.exceptions.append(f"Update_pulse failed for the cluster {cluster_info} with the error: {e}")

    def verify(self):
        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                pe_session = cluster_details["pe_session"]

                self.results["clusters"][cluster_ip] = {
                    "Change_Default_password": "CAN'T VERIFY",
                    "Accept_Eula": "CAN'T VERIFY",
                    "Update_Pulse": "CAN'T VERIFY"
                }

                # Check if password is changed
                try:
                    endpoint = "cluster"
                    default_pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                                     pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                                     port="9440", secured=True)
                    cluster_obj = PeCluster(default_pe_session)
                    cluster_obj.read(endpoint=endpoint)
                except Exception:
                    # if it fails, i.e default password doesn't work, password is changed
                    self.results["clusters"][cluster_ip]["Change_Default_password"] = "PASS"

                # Check if Eula is accepted
                eula = Eula(pe_session)

                if eula.is_eula_accepted():
                    self.results["clusters"][cluster_ip]["Accept_Eula"] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Accept_Eula"] = "FAIL"

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
                self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' for "
                                 f"{cluster_ip}")
