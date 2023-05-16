from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class StoragePool(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/storage_pools"
        self.session = session
        super(StoragePool, self).__init__(session=session)
