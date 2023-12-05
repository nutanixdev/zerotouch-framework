from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v2 import PeEntityV2


class Cluster(PeEntityV2):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/cluster"
        self.cluster_info = {}
        super(Cluster, self).__init__(session=session)

    def get_cluster_info(self):
        return self.cluster_info.update(self.read())

    def update_dsip(self, dsip: str):
        cluster_config = self.read()
        data = {
            "cluster_external_data_services_ipaddress": dsip
        }
        cluster_config.update(data)
        return self.update(data=cluster_config)
