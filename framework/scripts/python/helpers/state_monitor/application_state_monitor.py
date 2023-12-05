from typing import Optional, Dict
from framework.helpers.log_utils import get_logger
from .state_monitor import StateMonitor
from ..v3.application import Application

logger = get_logger(__name__)


class ApplicationStateMonitor(StateMonitor):
    """
    The class to monitor the application state.
    """
    DEFAULT_TIMEOUT_IN_SEC = 20*60
    DEFAULT_CHECK_INTERVAL_IN_SEC = 120

    def __init__(self, session, **kwargs):
        """
        The constructor for ApplicationStateMonitor
        Args:
          session: request session to query the API
          kwargs:
            expected_states(list): expected states of application
              NOTE: default value is ['running']
            unexpected_states(list): unexpected states of entity
              NOTE: default value is ['error']
            application_uuid(str): uuid of application
            application_op(ApplicationOp): application entity op.
        """
        self.session = session
        self._expected_states = kwargs.get('expected_states', ['running'])
        self._unexpected_states = kwargs.get('unexpected_states', ['error'])
        self._application_uuid = kwargs.get('application_uuid')

    def check_status(self) -> (Optional[Dict], bool):
        """
        Checks the state if "application_uuid" is among "expected_states"

        Returns:
          True if entity in required states
          False if entity is not in required states within timeout.
        """

        application_op = Application(self.session)
        response = application_op.read(uuid=self._application_uuid)

        if response and response.get('status'):
            status = response['status']['state']
        else:
            logger.error("Error in the response from the API call")
            return None, False

        if status in self._unexpected_states:
            logger.error(f"State for application with uuid [{self._application_uuid}] is not expected."
                         "\nState of this application is [{status}]")
            return None, True
        elif status in self._expected_states:
            logger.info(f"State on Application deployment changed successfully to [{status}]")
            return response, True
        else:
            logger.warning("Application state did not match the expected state")
            return None, False
