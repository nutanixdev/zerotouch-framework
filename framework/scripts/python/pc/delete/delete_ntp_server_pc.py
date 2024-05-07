from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.cluster import Cluster as PcCluster
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteNtpServersPc(Script):
    """
    Class that deletes NTP servers in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.ntp_servers_list = self.data.get("pc_ntp_servers_list") or self.data.get("ntp_servers_list", [])
        super(DeleteNtpServersPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            # Use v1 with PC url
            pc_cluster = PcCluster(self.pc_session)

            if self.ntp_servers_list:
                self.logger.info(f"Deleting NTP servers in {self.data['pc_ip']!r}")

                response = pc_cluster.delete_ntp_servers(self.ntp_servers_list)
                if response.get("value"):
                    self.logger.info(f"Deleting NTP servers {self.ntp_servers_list} successful!")
                else:
                    raise Exception(f"Could not Delete NTP servers {self.ntp_servers_list}")
            else:
                self.logger.info(f"No NTP servers to delete in {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.ntp_servers_list:
            return

        # Initial status
        self.results["DeleteNTPServersPc"] = {}

        # Use v1 with PC url
        pc_cluster = PcCluster(self.pc_session)
        current_ntp_servers_list = []

        for ntp_server in self.ntp_servers_list:
            # Initial status
            self.results["DeleteNTPServersPc"][ntp_server] = "CAN'T VERIFY"

            current_ntp_servers_list = current_ntp_servers_list or pc_cluster.get_ntp_servers()
            if ntp_server not in current_ntp_servers_list:
                self.results["DeleteNTPServersPc"][ntp_server] = "PASS"
            else:
                self.results["DeleteNTPServersPc"][ntp_server] = "FAIL"
