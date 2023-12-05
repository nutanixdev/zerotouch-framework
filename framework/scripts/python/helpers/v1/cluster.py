from typing import List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Cluster(PeEntityV1):
    """
    v1 version of cluster API
    """
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/cluster"
        super(Cluster, self).__init__(session=session)

    def add_name_servers(self, name_server_list: List) -> Dict:
        """
        Add given name servers to PC/PE.
        Need to initialize with v1 version "cluster"
        """
        return self.create(
            data=name_server_list,
            endpoint="name_servers/add_list"
        )

    def get_name_servers(self) -> List:
        """
        Get name servers of PC/PE. Need to initialize with v1 version "cluster"
        Returns:
          response (list): name server ip list
        """
        return self.read(
            endpoint="name_servers"
        )

    def add_ntp_servers(self, ntp_server_list: List) -> Dict:
        """
        Add given NTP servers to PC/PE. Need to initialize with v1 version "cluster"
        """
        return self.create(
            data=ntp_server_list,
            endpoint="ntp_servers/add_list"
        )

    def get_ntp_servers(self) -> List:
        """
        Get ntp servers of PC/PE. Need to initialize with v1 version "cluster"
        Returns:
          response (list): ntp servers list
        """
        return self.read(
            endpoint="ntp_servers"
        )
