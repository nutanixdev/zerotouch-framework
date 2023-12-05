from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity import PcEntity


class PrismCentral(PcEntity):
    kind = "prism_central"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/prism_central"
        super(PrismCentral, self).__init__(session=session)
