from ..pe_entity_v2 import PeEntityV2
from framework.helpers.rest_utils import RestAPIUtil

class VM(PeEntityV2):
    kind = "vm"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/vms"
        self.session = session
        super(VM, self).__init__(session=session)