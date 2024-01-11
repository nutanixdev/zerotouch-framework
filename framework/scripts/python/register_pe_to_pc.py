from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .helpers.state_monitor.pc_register_monitor import PcRegisterMonitor
from .helpers.v1.multicluster import MultiCluster
from .helpers.v2.cluster import Cluster as PeCluster
from .cluster_script import ClusterScript
from .helpers.v3.cluster import Cluster as PcCluster

logger = get_logger(__name__)


class RegisterToPc(ClusterScript):
    """
    Class that takes multiple clusters and registers them to PC
    """
    SYNC_TIME = 300

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_ip = self.data["pc_ip"]
        self.pc_session = self.data["pc_session"]
        self.pe_uuids = []
        super(RegisterToPc, self).__init__(data, **kwargs)
        self.logger = self.logger or logger
        self.max_workers = 15

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        # get Cluster UUIDs
        # self.logger.info(f"Getting the UUID of the cluster {cluster_ip}...")
        if not cluster_details.get("cluster_info", {}).get("uuid"):
            cluster = PeCluster(pe_session)
            cluster.get_cluster_info()
            cluster_details["cluster_info"].update(cluster.cluster_info)

        try:
            status = self.register_cluster(cluster_ip, pe_session)
            if status:
                self.pe_uuids.append(cluster_details["cluster_info"]["uuid"])

            # Only for PEs that actually is going through registration, wait for the process to complete
            if self.pe_uuids:
                # Monitor PC registration - Checks given PE clusters are successfully
                # registered to PC.
                app_response, status = PcRegisterMonitor(self.pc_session,
                                                         pe_uuids=self.pe_uuids).monitor()

                if not status:
                    self.exceptions.append(
                        "Timed out. Registration of clusters to PC didn't happen in the prescribed timeframe")
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
                self.logger.warning(f"Cluster '{pe_ip}' is already registered to a PC with IP: '{pc_ip}'")
                return False

        response = cluster.register_pe_to_pc(pc_ip=self.pc_ip,
                                             pc_username=self.data["pc_username"],
                                             pc_password=self.data["pc_password"])

        exception_msg = f"Failed to register {pe_ip}. Got the following response for " \
                        f"'add_to_multicluster' API: {response}"

        status = False
        if isinstance(response, dict):
            value = response.get("value", None)
            if not value:
                self.exceptions.append(exception_msg)
            else:
                status = True
        elif isinstance(response, str):
            if "Already added to multi-cluster" not in response:
                self.exceptions.append(exception_msg)
        else:
            self.exceptions.append(exception_msg)

        return status

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check which clusters failed
        try:
            self.results["clusters"][cluster_ip] = {
                "Register_to_PC": "CAN'T VERIFY"
            }
            cluster_uuid = cluster_details["cluster_info"]["uuid"]

            pc_cluster = PcCluster(self.pc_session)
            pc_cluster.get_pe_info_list()
            pc_cluster_uuids = pc_cluster.name_uuid_map.values()

            if cluster_uuid in pc_cluster_uuids:
                self.results["clusters"][cluster_ip]["Register_to_PC"] = "PASS"
            else:
                self.results["clusters"][cluster_ip]["Register_to_PC"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' "
                             f"for {cluster_ip}")
