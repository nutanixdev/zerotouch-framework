from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.v1.cluster import Cluster as PcCluster
from .script import Script

logger = get_logger(__name__)


class AddNtpServersPc(Script):
    """
    Class that adds NTP servers in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.ntp_servers_list = self.data.get("pc_ntp_servers_list") or self.data.get("ntp_servers_list", [])
        super(AddNtpServersPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            # Use v1 with PC url
            pc_cluster = PcCluster(self.pc_session)

            if self.ntp_servers_list:
                self.logger.info(f"Adding NTP servers in '{self.data['pc_ip']}'")

                response = pc_cluster.add_ntp_servers(self.ntp_servers_list)
                if response["value"]:
                    self.logger.info(f"Adding NTP servers {self.ntp_servers_list} successful!")
                else:
                    raise Exception(f"Could not add NTP servers {self.ntp_servers_list}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.ntp_servers_list:
            return

        # Initial status
        self.results["NTPServers"] = {}

        # Use v1 with PC url
        pc_cluster = PcCluster(self.pc_session)
        current_ntp_servers_list = []

        for ntp_server in self.ntp_servers_list:
            # Initial status
            self.results["NTPServers"][ntp_server] = "CAN'T VERIFY"

            current_ntp_servers_list = current_ntp_servers_list or pc_cluster.get_ntp_servers()
            if ntp_server in current_ntp_servers_list:
                self.results["NTPServers"][ntp_server] = "PASS"
            else:
                self.results["NTPServers"][ntp_server] = "FAIL"
