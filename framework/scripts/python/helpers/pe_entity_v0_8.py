from framework.helpers.rest_utils import RestAPIUtil
from .pe_entity import PeEntity


class PeEntityV0_8(PeEntity):
    version = "v0.8"
    resource_type = ""

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        super(PeEntityV0_8, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)
