from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.v1.cluster import Cluster as PcCluster
from .script import Script

logger = get_logger(__name__)


class AddNameServersPc(Script):
    """
    Class that adds nameservers in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.name_servers_list = self.data.get("pc_name_servers_list") or self.data.get("name_servers_list", [])
        super(AddNameServersPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            # Use v1 with PC url
            pc_cluster = PcCluster(self.pc_session)

            if self.name_servers_list:
                self.logger.info(f"Adding name servers in '{self.data['pc_ip']}'")
                response = pc_cluster.add_name_servers(self.name_servers_list)
                if response["value"]:
                    self.logger.info(f"Adding name servers {self.name_servers_list} successful!")
                else:
                    raise Exception(f"Could not add name servers {self.name_servers_list}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.name_servers_list:
            return

        # Initial status
        self.results["NameServers"] = {}

        # Use v1 with PC url
        pc_cluster = PcCluster(self.pc_session)
        current_name_servers_list = []

        for name_server in self.name_servers_list:
            # Initial status
            self.results["NameServers"][name_server] = "CAN'T VERIFY"

            current_name_servers_list = current_name_servers_list or pc_cluster.get_name_servers()
            if name_server in current_name_servers_list:
                self.results["NameServers"][name_server] = "PASS"
            else:
                self.results["NameServers"][name_server] = "FAIL"
