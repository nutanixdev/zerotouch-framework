from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from scripts.python.helpers.v3.blueprint import Blueprint

logger = get_logger(__name__)


class BlueprintLaunchMonitor(StateMonitor):
    """
  The class to wait for blueprint launch status to come in expected state
  """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 300

    def __init__(self, session: RestAPIUtil, **kwargs):
        """
        The constructor for BlueprintLaunchMonitor
        Args:
          kwargs:
            session: request session to query the API
            expected_state(str): expected state of blueprint launch required
            blueprint_uuid(str): uuid of blueprint
            request_id(str): id of launch request
        """
        self.session = session
        self.expected_state = kwargs.get('expected_state', 'success')
        self.blueprint_uuid = kwargs.get('blueprint_uuid')
        self.request_id = kwargs.get('request_id')

    def check_status(self):
        """
        Checks the state of blueprint launch if expected state or not
        Returns:
          True if in expected state else false
        """
        blueprint_op = Blueprint(self.session)
        response = blueprint_op.read(uuid=self.blueprint_uuid, endpoint=f"pending_launches/{self.request_id}")

        if response and response.get('status'):
            status = response['status']['state']
        else:
            logger.error("Error in the response from the API call")
            return None, False

        if status != self.expected_state:
            logger.warning("Blueprint launch did not match the expected state")
            return None, False
        else:
            logger.info(f"State on Blueprint launch changed successfully to [{status}]")
            return response, True
