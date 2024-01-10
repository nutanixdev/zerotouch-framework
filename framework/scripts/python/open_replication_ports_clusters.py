from typing import Dict
from framework.helpers.log_utils import get_logger
from .cluster_script import ClusterScript
from .helpers.ssh_cvm import SSHCVM

logger = get_logger(__name__)


class OpenRepPort(ClusterScript):
    """
    The Script to add Open Replication port in a cluster
    """

    def __init__(self, data: Dict, **kwargs):
        super(OpenRepPort, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        self.results["clusters"][cluster_ip] = {
            "Open_Replication_ports": "CAN'T VERIFY"
        }

        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
        try:
            cvm_session = SSHCVM(cvm_ip=cluster_ip, cvm_password="RDMCluster.123")
            self.logger.info(f"{cluster_ip} - Opening replication ports '2020, 2030, 2036, 2073, 2090'")
            out, err = cvm_session.enable_replication_ports()
            # self.logger.info(out)
            if err:
                # todo need to find a way to fix this
                self.results["clusters"][cluster_ip]["Open_Replication_ports"] = "FAIL"
                raise Exception(err)
            else:
                self.results["clusters"][cluster_ip]["Open_Replication_ports"] = "PASS"
                self.logger.info(f"{cluster_ip} - Opened the ports in all the CVMs")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                   f"with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # How do we verify?
        pass
