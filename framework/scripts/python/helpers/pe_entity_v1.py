from framework.helpers.rest_utils import RestAPIUtil
from .pe_entity import PeEntity


class PeEntityV1(PeEntity):
    version = "v1"
    resource_type = ""

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        super(PeEntityV1, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)
