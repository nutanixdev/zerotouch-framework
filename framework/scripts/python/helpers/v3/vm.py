from copy import deepcopy
from scripts.python.helpers.pc_entity import PcEntity
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class VM(PcEntity):
    kind = "vm"

    def __init__(self, session):
        self.resource_type = "/vms"
        super(VM, self).__init__(session)
