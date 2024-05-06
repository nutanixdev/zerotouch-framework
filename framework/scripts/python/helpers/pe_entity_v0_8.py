from framework.helpers.rest_utils import RestAPIUtil
from .entity import Entity


class PeEntityV0_8(Entity):
    __BASEURL__ = "api/nutanix/v0.8"
    resource_type = ""

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        resource_type = self.__BASEURL__ + self.resource_type
        self.proxy_cluster_uuid = proxy_cluster_uuid
        super(PeEntityV0_8, self).__init__(session=session, resource_type=resource_type)

    # """
    # This method uses available fan-out API in PE. These APIs are not documented for external use
    # but are used by the PE UI extensively.
    # api_version: v0.8
    # """
    def get_proxy_endpoint(self, endpoint):
        if self.proxy_cluster_uuid:
            separator = "&" if "?" in endpoint else "?"
            endpoint = f"{endpoint}{separator}proxyClusterUuid={self.proxy_cluster_uuid}"
        return endpoint

    def read(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super(PeEntityV0_8, self).read(endpoint=endpoint, **kwargs)

    def create(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super(PeEntityV0_8, self).create(endpoint=endpoint, **kwargs)

    def update(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super(PeEntityV0_8, self).update(endpoint=endpoint, **kwargs)
