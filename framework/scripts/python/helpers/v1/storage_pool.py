from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class StoragePool(PeEntityV1):
    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/storage_pools"
        self.session = session
        super(StoragePool, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)
