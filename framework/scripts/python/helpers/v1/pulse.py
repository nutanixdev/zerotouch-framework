import logging

from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1

logger = get_logger(__name__)


class Pulse(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/pulse"
        super(Pulse, self).__init__(session=session)

    def update_pulse(self, cluster_info: str, enable: bool = True):
        """Enable/disable Pulse

        Args:
            enable (bool, optional): Enable or Disable Pulse in PE. Defaults to True.
            cluster_info
        """
        data = {
            "enable": enable,
            "isPulsePromptNeeded": False
            }

        # get current status
        current_status = self.read().get("enable")

        if current_status == enable:
            logger.warning(f"Pulse is already '{enable}' in the cluster {cluster_info}")
        self.update(data=data)
