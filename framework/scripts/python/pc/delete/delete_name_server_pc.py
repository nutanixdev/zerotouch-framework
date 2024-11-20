from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.cluster import Cluster as PcCluster
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class DeleteNameServersPc(Script):
    """
    Class that deletes nameservers in PC
    """
    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = self.data["pc_session"]
        self.name_servers_list = self.data.get("pc_name_servers_list") or self.data.get("name_servers_list", [])
        super(DeleteNameServersPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            # Use v1 with PC url
            pc_cluster = PcCluster(self.pc_session)

            if self.name_servers_list:
                self.logger.info(f"Deleting name servers in {self.data['pc_ip']!r}")
                response = pc_cluster.delete_name_servers(self.name_servers_list)
                if response.get("value"):
                    self.logger.info(f"Deleting name servers {self.name_servers_list} successful!")
                else:
                    raise Exception(f"Could not delete name servers {self.name_servers_list}")
            else:
                self.logger.info(f"No name servers to delete in {self.data['pc_ip']!r}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.name_servers_list:
            return

        # Initial status
        self.results["DeleteNameServersPc"] = {}

        # Use v1 with PC url
        pc_cluster = PcCluster(self.pc_session)
        current_name_servers_list = []

        for name_server in self.name_servers_list:
            # Initial status
            self.results["DeleteNameServersPc"][name_server] = "CAN'T VERIFY"

            current_name_servers_list = current_name_servers_list or pc_cluster.get_name_servers()
            if name_server not in current_name_servers_list:
                self.results["DeleteNameServersPc"][name_server] = "PASS"
            else:
                self.results["DeleteNameServersPc"][name_server] = "FAIL"
