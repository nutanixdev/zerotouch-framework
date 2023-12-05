from ..entity import Entity


class Karbon(Entity):
    __BASEURL__ = "karbon"

    def __init__(self, session, resource_type):
        resource_type = self.__BASEURL__ + resource_type
        super(Karbon, self).__init__(session=session, resource_type=resource_type)
