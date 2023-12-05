from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Pulse(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/pulse"
        super(Pulse, self).__init__(session=session)

    def update_pulse(self, enable: bool = True):
        """Enable/disable Pulse

        Args:
            enable (bool, optional): Enable or Disable Pulse in PE. Defaults to True.
        """
        data = {
            "enable": enable,
            "isPulsePromptNeeded": False
        }

        self.update(data=data)
