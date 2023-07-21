from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_v1.genesis import Genesis
from scripts.python.helpers.state_monitor.state_monitor import StateMonitor

logger = get_logger(__name__)


class KarbonEnabledMonitor(StateMonitor):
    """
    The class to wait for Karbon to be enabled
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 300

    def __init__(self, session: RestAPIUtil):
        """
        The constructor for TaskMonitor
        Args:
        session: request pc session to query the API
        """
        self.session = session

    def check_status(self):
        """
        Checks the task is in expected state or not
        Returns:
          True if in expected state else false
        """
        genesis = Genesis(self.session)

        # Only checking for UI service
        # todo need to check for Karbon core service as well
        status, _ = genesis.enable_karbon()

        return None, status
