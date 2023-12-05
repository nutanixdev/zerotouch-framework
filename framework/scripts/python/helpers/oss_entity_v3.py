from framework.helpers.rest_utils import RestAPIUtil
from .entity import Entity
from .pc_groups_op import PcGroupsOp


class OssEntityOp(Entity):
    """
    The parent class for all OSS related entities like bucket, etc.
    1. Using V3 API by default
    2. Use V3 list by default
    """
    # For all the OSS REST API call, we need to pass the base_path
    __BASEURL__ = "oss/api/nutanix/v3"
    resource_type = ""
    kind = None

    def __init__(self, session: RestAPIUtil):
        resource_type = self.__BASEURL__ + self.resource_type
        super(OssEntityOp, self).__init__(session=session, resource_type=resource_type)

    def list(self, **kwargs):
        """
        List the entity by groups call
        Args(kwargs):
          entity_type(str, optional): The type of the entity
          attributes(list): The list of attributes of the entity to return.
          base_path(str, optional): The base path for the API
          query_str(str, optional): The query string for the url
        Returns:
          list, the list of entity
        """
        response = PcGroupsOp(self.session, base_path=kwargs.get("base_path", self.__BASEURL__)).list_entities(
            entity_type=kwargs.pop("entity_type", self.kind),
            attributes=kwargs.pop("attributes", []),
            filter_criteria=kwargs.pop("filter_criteria", None),
            **kwargs
        )
        return response
