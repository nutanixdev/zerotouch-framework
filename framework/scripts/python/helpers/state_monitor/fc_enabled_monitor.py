from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_v1.genesis import Genesis
from .state_monitor import StateMonitor

logger = get_logger(__name__)


class FcEnabledMonitor(StateMonitor):
    """
    The class to wait for Foundation Central to be enabled
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

        status, _ = genesis.is_fc_enabled()

        return None, status
