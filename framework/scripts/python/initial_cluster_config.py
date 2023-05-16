import time
from scripts.python.cluster_script import ClusterScript
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.v1.utils_manager import UtilsManager
from scripts.python.helpers.v1.eula import Eula
from scripts.python.helpers.v1.pulse import Pulse
from scripts.python.helpers.v2.cluster import Cluster as PeCluster
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class InitialClusterConfig(ClusterScript):
    """
    Accept Eula
    Enable Pulse
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: dict, **kwargs):
        super(InitialClusterConfig, self).__init__(data, **kwargs)

    @staticmethod
    def change_default_password(pe_session: RestAPIUtil, new_pe_password: str, cluster_info):
        default_system_password = UtilsManager(pe_session)
        default_system_password.change_default_system_password(new_pe_password, cluster_info)
        # Waiting for password sync
        time.sleep(30)

    @staticmethod
    def accept_eula(pe_session: RestAPIUtil, data: dict, cluster_info):
        eula = Eula(pe_session)

        if eula.is_eula_accepted():
            logger.warning(f"Eula is already accepted for the cluster {cluster_info}")
            return
        eula.accept_eula(**data, cluster_info=cluster_info)

    @staticmethod
    def update_pulse(pe_session: RestAPIUtil, enable_pulse: bool, cluster_info):
        pulse = Pulse(session=pe_session)
        pulse.update_pulse(enable=enable_pulse, cluster_info=cluster_info)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        new_pe_password = cluster_details.get("pe_password")

        if new_pe_password == self.DEFAULT_SYSTEM_PASSWORD:
            logger.error(f"New Password specified is same as default password for the cluster ...")
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
        # default password shouldn't work
        cluster_list = []
        endpoint = "cluster"
        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                default_pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                                 pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                                 port="9440", secured=True)
                cluster_obj = PeCluster(default_pe_session)
                cluster_obj.read(endpoint=endpoint)
            except Exception:
                # if it fails, i.e default password doesn't work, password is changed
                continue
            cluster_list.append(cluster_ip)

        if cluster_list:
            logger.warning(f"Password change failed for the clusters: {cluster_list}")
