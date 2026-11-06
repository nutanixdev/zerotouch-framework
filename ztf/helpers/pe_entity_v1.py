from ztf.helpers.pe_entity import PeEntity
from ztf.helpers.utils.rest_utils import RestAPIUtil


class PeEntityV1(PeEntity):
    version = "v1"
    resource_type = ""

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid: str | None = None):
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)
