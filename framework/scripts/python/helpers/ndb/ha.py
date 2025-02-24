from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class HA(NDB):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/ha"
        super(HA, self).__init__(session)

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

    def get_vip(self, ndb_ip) -> Dict:
        """
        Get the VIP of the NDB host
        Args:
            ndb_ip: The IP address of the NDB host
        Returns:
            dict: The VIP
        """
        endpoint = "i/vip/fqdn-resolve"
        query = {
            "fqdn": ndb_ip
        }
        return super().read(endpoint=endpoint, query=query)

    def enable(self, cluster_id: str, compute_profile_id: str, network_profile_id: str, prefix: str = "NDB") -> Dict:
        """
        Enable HA
        Args:
          cluster_id(str): The cluster id
          compute_profile_id(str): The compute profile id
          network_profile_id(str): The network profile id
          prefix(str, optional): The prefix for HA VMs
        Returns:
          dict, The API response
        """
        endpoint = "enable"
        num_db_vm = 3
        num_api_vm = 2
        num_proxy_vm = 2

        payload = {
            "computeProfileId": compute_profile_id,
            "networkProfileId": network_profile_id,
            "networkProfileIdForLoadBalancers": network_profile_id,
            "nodes": []
        }

        payload["nodes"].extend([{
            "vmName": f"{prefix}_pg_{i}",
            "nxClusterId": cluster_id,
            "properties": [{"name": "node_type", "value": "database"}]
        } for i in range(1, num_db_vm + 1)])

        payload["nodes"].extend([{
            "vmName": f"{prefix}_api_server_{i}",
            "nxClusterId": cluster_id,
            "properties": [{"name": "node_type", "value": "api_server"}]
        } for i in range(1, num_api_vm + 1)])

        payload["nodes"].extend([{
            "vmName": f"{prefix}_haproxy_{i}",
            "nxClusterId": cluster_id,
            "properties": [{"name": "node_type", "value": "haproxy"}]
        } for i in range(1, num_proxy_vm + 1)])

        return super().create(data=payload, endpoint=endpoint)
