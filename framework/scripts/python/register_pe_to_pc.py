from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.pc_register_monitor import PcRegisterMonitor
from scripts.python.helpers.v1.multicluster import MultiCluster
from scripts.python.helpers.v2.cluster import Cluster as PeCluster
from scripts.python.cluster_script import ClusterScript

logger = get_logger(__name__)


class RegisterToPc(ClusterScript):
    """
    Class that takes multiple clusters and registers them to PC
    """
    SYNC_TIME = 300

    def __init__(self, data: dict, **kwargs):
        self.data = data
        self.pc_ip = self.data["pc_ip"]
        self.pc_session = self.data["pc_session"]
        self.pe_uuids = []
        super(RegisterToPc, self).__init__(data, **kwargs)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        # get Cluster UUIDs
        # logger.info(f"Getting the UUID of the cluster {cluster_ip}...")
        if not cluster_details.get("cluster_info", {}).get("uuid"):
            cluster = PeCluster(pe_session)
            cluster.get_cluster_info()
            cluster_details["cluster_info"].update(cluster.cluster_info)
        self.pe_uuids.append(cluster_details["cluster_info"]["uuid"])

        try:
            _ = self.register_cluster(cluster_ip, pe_session)
        except Exception as e:
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                   f"with the error: {e}")

    def register_cluster(self, pe_ip: str, pe_session: RestAPIUtil) -> bool:
        cluster = MultiCluster(pe_session)

        # check if cluster is already registered to a PC
        response = cluster.get_cluster_external_state()

        if response:
            pc_ip = ""
            for data in response:
                if data.get('clusterDetails'):
                    pc_ip = data['clusterDetails'].get("ipAddresses", [None])[0]

            if pc_ip:
                logger.warning(f"Cluster {pe_ip} is already registered to a PC with IP: {pc_ip}")
                return False

        response = cluster.register_pe_to_pc(pe_ip=pe_ip,
                                             pc_ip=self.pc_ip,
                                             pc_username=self.data["pc_username"],
                                             pc_password=self.data["pc_password"])

        exception_msg = f"Failed to register {pe_ip}. Got the following response for " \
                        f"'add_to_multicluster' API: {response}"
        if isinstance(response, dict):
            value = response.get("value", None)
            if not value:
                self.exceptions.append(exception_msg)
        elif isinstance(response, str):
            if "Already added to multi-cluster" not in response:
                self.exceptions.append(exception_msg)
        else:
            self.exceptions.append(exception_msg)

        return True

    def verify(self, **kwargs):
        # Monitor PC registration - Checks given PE clusters are successfully
        # registered to PC.
        app_response, status = PcRegisterMonitor(self.pc_session,
                                                 pe_uuids=self.pe_uuids).monitor()

        if not status:
            self.exceptions.append("Timed out. Registration of clusters to PC didn't happen in the prescribed timeframe")
