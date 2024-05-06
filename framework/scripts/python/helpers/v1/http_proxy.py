from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class HttpProxy(PeEntityV1):
    """
    Class to create/update/delete/read http proxy
    """

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/http_proxies"
        super(HttpProxy, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    @staticmethod
    def get_payload(**kwargs):
        return {
            "address": kwargs.get("address", None),
            "addressValue": kwargs.get("address_value", None),
            "name": kwargs.get("name", None),
            "password": kwargs.get("password", None),
            "port": kwargs.get("port", None),
            "proxyTypes": kwargs.get("proxy_types", []),
            "username": kwargs.get("username", None)
        }

    def create(self, **kwargs) -> dict:
        return super().create(data=self.get_payload(**kwargs))

    def update(self, **kwargs):
        super().update(data=self.get_payload(**kwargs))
