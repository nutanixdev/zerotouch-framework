from typing import List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Cluster(PeEntityV1):
    """
    v1 version of cluster API
    """

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/cluster"
        super(Cluster, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def add_name_servers(self, name_server_list: List) -> Dict:
        """
        Add given name servers to PC/PE.
        Need to initialize with v1 version "cluster"
        """
        return self.create(
            data=name_server_list,
            endpoint="name_servers/add_list"
        )

    def delete_name_servers(self, name_server_list: List) -> Dict:
        """
        Delete given name servers from PC/PE.
        Need to initialize with v1 version "cluster"
        """
        # Using Create Method since remove list is a POST request
        return self.create(
            data=name_server_list,
            endpoint="name_servers/remove_list"
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

    def delete_ntp_servers(self, ntp_server_list: List):
        """
        Delete given NTP Servers from PC/PE
        """
        # Using Create Method since remove list is a POST request
        return self.create(
            data=ntp_server_list,
            endpoint="ntp_servers/remove_list"
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

    def update_rebuild_reservation(self, enable: bool) -> Dict:
        """
        Enable/Disable Rebuild Reservation in PE. Need to initialize with v1 version "cluster"
        PATCH method is used to update Rebuild in cluster
        Args:
          enable (bool): Enable Rebuild Reservation if True. Disable if False.
        Returns:
          response (dict)
        """
        return self.update(
            data={"enableRebuildReservation": enable},
            method="PATCH"
        )

    def get_smptp_config(self) -> Dict:
        """
        Get SMPTP config of PC/PE. Need to initialize with v1 version "cluster"
        Returns:
          response (dict): SMPTP config
        """
        return self.read(endpoint="smtp")

    def update_smptp_config(self, address, port, fromEmailAddress,  secureMode="NONE", addressValue=None, **kwargs) -> Dict:
        """
        Update SMPTP config of PC/PE. Need to initialize with v1 version "cluster"
        Returns:
          response (dict): SMPTP config
        """
        data = {
            "address": address,
            "port": port,
            "secureMode": secureMode,
            "fromEmailAddress": fromEmailAddress
        }
        if addressValue:
            data["addressValue"] = addressValue
        if secureMode != "NONE":
            data["username"] = kwargs.get("username", None)
            data["password"] = kwargs.get("password", None)
        return self.update(data=data, endpoint="smtp")
