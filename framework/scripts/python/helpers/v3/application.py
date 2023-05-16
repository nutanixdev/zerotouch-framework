from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity


class Application(PcEntity):
    kind = "app"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/apps"
        super(Application, self).__init__(session=session)
