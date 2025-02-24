from typing import Optional

from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..ndb.operations import Operation

logger = get_logger(__name__)


class NdbTaskMonitor(StateMonitor):
    """
    Class to wait for virtual ip address of NDB
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 60
    DEFAULT_TIMEOUT_IN_SEC = 30 * 60

    def __init__(self, session: RestAPIUtil, task_id: Optional[str] = None, operation_name: Optional[str] = None,
                 success_percentage: int = 100):
        """
          The constructor for NdbVipMonitor
          Args:
            session: request session to query the API
            task_id: The Task ID to monitor
            success_percentage: The percentage of task completion to consider as success
          """
        self.session = session
        self.task_id = task_id
        self.success_percentage = success_percentage
        self.operation_op = Operation(self.session)

    def check_status(self):
        """
        Check whether NDB Task is completed

        Returns:
          bool: True
        """
        response = None
        completed = False

        try:
            response = self.operation_op.get_operation_by_uuid(self.task_id)
            if response.get("id") == self.task_id:
                logger.info(f"Percentage Complete: {response.get('percentageComplete')}/{self.success_percentage}")
                if int(response.get("percentageComplete")) >= self.success_percentage:
                    completed = True
            else:
                completed = True
                response = None
        except Exception as e:
            logger.error(f"Error while checking NDB Task status: {e}")
        return response, completed
