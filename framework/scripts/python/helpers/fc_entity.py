from .entity import Entity


class FcEntity(Entity):
    __BASEURL__ = "api/fc/v1"

    def __init__(self, session, resource_type):
        resource_type = self.__BASEURL__ + resource_type
        super(FcEntity, self).__init__(
            session=session, resource_type=resource_type)
