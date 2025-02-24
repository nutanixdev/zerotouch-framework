from framework.helpers.rest_utils import RestAPIUtil
from .entity import Entity


class NDB(Entity):
    __BASEURL__ = "era/v0.9"
    resource_type = ""
    kind = ""

    def __init__(self, session: RestAPIUtil, **kwargs):
        resource_type = self.__BASEURL__ + self.resource_type
        super(NDB, self).__init__(session=session, resource_type=resource_type)
