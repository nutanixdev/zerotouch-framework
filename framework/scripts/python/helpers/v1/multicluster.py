from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class MultiCluster(PeEntityV1):

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/multicluster"
        super(MultiCluster, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def get_cluster_external_state(self):
        """
        Get cluster external state
        """
        endpoint = "cluster_external_state"
        return self.read(endpoint=endpoint)

    def register_pe_to_pc(self, pc_ip, pc_username, pc_password) -> Dict:
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }

        endpoint = "add_to_multicluster"
        return self.create(data=data, endpoint=endpoint)

    def deregister_pe_from_pc(self, pc_ip, pc_username, pc_password) -> Dict:
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }

        endpoint = "remove_from_multicluster"
        return self.create(data=data, endpoint=endpoint)
