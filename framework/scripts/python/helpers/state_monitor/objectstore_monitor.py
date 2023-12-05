from typing import List

from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..objects.objectstore import ObjectStore

logger = get_logger(__name__)


class ObjectstoreMonitor(StateMonitor):
    """
    The class to wait for objectstore creation status to come in expected state
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 60
    DEFAULT_TIMEOUT_IN_SEC = 3600

    def __init__(self, session: RestAPIUtil, os_name: str):
        """
        The constructor for ObjectstoreMonitor
        Args:
            session: request session to query the API
            os_name: objectstore to monitor
        """
        self.session = session
        # List of possible states of tasks currently in progress.
        self.progress_states = ['PENDING', 'SCALING_OUT', 'REPLACING_CERT']
        self.os_name = os_name

    def check_status(self) -> (List, bool):
        """
        Check whether the given objectstores is not in progress(PENDING).
        Returns:
          bool: False if the object is PENDING, True otherwise.
        """
        # Initial status
        status = True
        os = ObjectStore(self.session)
        os_list = {object_store.get('name'): object_store.get('state') for object_store in os.list()}

        if self.os_name in os_list:
            if os_list[self.os_name] in self.progress_states:
                status = False

        return os_list, status
