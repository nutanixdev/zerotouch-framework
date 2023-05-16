from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class MultiCluster(PeEntityV1):

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/multicluster"
        super(MultiCluster, self).__init__(session=session)

    def get_cluster_external_state(self):
        """

        """
        endpoint = "cluster_external_state"
        return self.read(endpoint=endpoint, timeout=90)

    def register_pe_to_pc(self, pe_ip, pc_ip, pc_username, pc_password):
        logger.info("Registering PE {} to PC {}".format(pe_ip, pc_ip))
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }

        endpoint = "add_to_multicluster"
        return self.create(data=data, endpoint=endpoint, timeout=120)

    def deregister_pe_from_pc(self, pe_ip, pc_ip, pc_username, pc_password):
        logger.info("De-registering PE {} from PC {}".format(pe_ip, pc_ip))
        data = {
          "ipAddresses": [pc_ip],
          "username": pc_username,
          "password": pc_password
        }

        endpoint = "remove_from_multicluster"
        return self.create(data=data, endpoint=endpoint)
