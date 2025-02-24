from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..ndb.ha import HA

logger = get_logger(__name__)


class NdbVipMonitor(StateMonitor):
    """
    Class to wait for virtual ip address of NDB
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 30
    DEFAULT_TIMEOUT_IN_SEC = 5 * 60

    def __init__(self, session: RestAPIUtil, ndb_ip: str):
        """
          The constructor for NdbVipMonitor
          Args:
            session: request session to query the API
            ndb_ip: The IP address of the NDB VM
          """
        self.session = session
        self.ndb_ip = ndb_ip
        self.ha_op = HA(self.session)

    def check_status(self):
        """
        Check whether NDB VM has Virtual IP address

        Returns:
          bool: True
        """
        response = None
        completed = False

        try:
            response = self.ha_op.get_vip(self.ndb_ip)
            # if response.get("virtualIpAddress") != "NOT_AVAILABLE":
            completed = True
        except Exception as e:
            logger.error(f"Error while checking NDB VIP status: {e}")

        return response, completed
