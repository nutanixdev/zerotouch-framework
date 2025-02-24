from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class Resource(NDB):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/resources"
        super(Resource, self).__init__(session)

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        raise NotImplementedError(f"get_spec method is not implemented for {type(self).__name__}")

    def update(
        self,
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
        method="PUT"
    ):
        raise NotImplementedError(f"update method is not implemented for  {type(self).__name__}")

    def delete(
        self,
        uuid=None,
        timeout=None,
        endpoint=None,
        query=None,
    ):
        raise NotImplementedError(f"delete method is not implemented for  {type(self).__name__}")

    def read(
        self,
        uuid=None,
        method="GET",
        data=None,
        headers=None,
        endpoint=None,
        query=None,
        timeout=None,
        entity_type=None,
        custom_filters=None
    ):
        raise NotImplementedError(f"read method is not implemented for  {type(self).__name__}")

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        data=None,
        query=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        raise NotImplementedError("list method is not implemented for Auth")

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        raise NotImplementedError("upload method is not implemented for Auth")

    def refresh_network(self):
        """
        Refresh era networks
        Args: None
        Returns:
          list : The api response. List of VLANs.
        """
        endpoint = "networks/era-server"
        query = {"refresh": True}
        return super().read(endpoint=endpoint, query=query)

    def get_networks(self, cluster_id: Optional[str] = None) -> Dict:
        """
        Get era networks
        Args:
            cluster_id(str, optional): The id of the cluster
        Returns:
          list : The api response. List of VLANs.
        """
        endpoint = "networks/era-server"
        query = {
            "refresh": False,
            "detailed": True
        }
        return super().read(endpoint=endpoint, query=query)

    def get_vlan_network_by_name(self, network_name: str, cluster_id: Optional[str] = None):
        """
        Get vlan network by name
        Args:
          network_name(str): The name of the network
          cluster_id(str, optional): The id of the cluster
        Returns:
          dict: The API response
        """
        networks = self.get_networks(cluster_id=cluster_id)
        if not networks.get("vlans"):
            return {}
        for network in networks["vlans"]:
            if network.get("name") == network_name:
                return network
        return {}

    def create_dhcp_network(self, cluster_id: str, network_name: str):
        """
        Create dhcp network
        Args:
          cluster_id(str): The id of cluster
          network_name(str): The name of the network in prism cluster
        Returns:
          dict: The API response
        """
        payload = {
            "name": network_name,
            "type": "DHCP",
            "properties": [],
            "ipPools": [],
            "clusterId": cluster_id
        }
        endpoint = "networks"
        return super().create(endpoint=endpoint, data=payload)

    def create_static_network(self, cluster_id: str, network_name: str, default_gateway: str, subnet_mask: str,
                              primary_dns: str, ip_ranges: List, secondary_dns: str = "") -> Dict:
        """
        Create static network
        Args(kwargs):
          cluster_id(str): The id the cluster
          network_name(str): The name of network in prism cluster
          default_gateway(str): the default gateway
          subnet_mask(str): The subnet mask
          primary_dns(str): The primary dns
          secondary_dns(str, optional): The secondary dns
          ip_ranges(list): The list of ip ranges
        Returns:
          dict: The API response
        """
        payload = {
            "name": network_name,
            "type": "Static",
            "properties": [
                {"name": "VLAN_GATEWAY", "value": default_gateway},
                {"name": "VLAN_SUBNET_MASK", "value": subnet_mask},
                {"name": "VLAN_PRIMARY_DNS", "value": primary_dns},
                {"name": "VLAN_SECONDARY_DNS", "value": secondary_dns}
            ],
            "clusterId": cluster_id,
            "ipPools": []
        }
        for ip_range in ip_ranges:
            payload["ipPools"].append(
                {
                    "startIP": ip_range[0],
                    "endIP": ip_range[1]
                }
            )
        endpoint = "networks"
        return super().create(endpoint=endpoint, data=payload)
