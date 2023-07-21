from scripts.python.helpers.pc_entity import PcEntity


class VM(PcEntity):
    kind = "vm"

    def __init__(self, session):
        self.resource_type = "/vms"
        super(VM, self).__init__(session)
