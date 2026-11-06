from ztf.helpers.entity import Entity
from ztf.helpers.utils.rest_utils import RestAPIUtil


class PeEntity(Entity):
    __BASE_URL__ = "api/nutanix/"
    version = ""
    resource_type = ""

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid: str | None = None):
        resource_type = self.__BASE_URL__ + self.version + self.resource_type
        self.proxy_cluster_uuid = proxy_cluster_uuid
        super().__init__(session=session, resource_type=resource_type)

    """
    This method uses available fan-out API in PC. These APIs are not documented for external use but are used
    by the PC UI extensively. To access these APIs use the same URL as PE with the PC IP and additional query
    parameter proxyClusterUuid=all_clusters or pass the respective cluster uuid

    api_version: v1/v2
    """

    def get_proxy_endpoint(self, endpoint: str) -> str:
        if self.proxy_cluster_uuid:
            separator = "&" if "?" in endpoint else "?"
            endpoint = (
                f"{endpoint}{separator}proxyClusterUuid={self.proxy_cluster_uuid}"
            )
        return endpoint

    def read(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super().read(endpoint=endpoint, **kwargs)

    def create(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super().create(endpoint=endpoint, **kwargs)

    def update(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super().update(endpoint=endpoint, **kwargs)

    def delete(self, **kwargs):
        endpoint = self.get_proxy_endpoint(kwargs.pop("endpoint", ""))
        return super().delete(endpoint=endpoint, **kwargs)
