from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..v3.service import Service


class ObjectsEnabledMonitor(StateMonitor):
    """
    The class to wait for objects service to enable
    """
    DEFAULT_TIMEOUT_IN_SEC = 1800
    DEFAULT_CHECK_INTERVAL_IN_SEC = 10

    def __init__(self, pc_session: RestAPIUtil):
        """
        Initialize the RpjStatusMonitor object.

        Args:
        pc_cluster(PrismCentralCluster): The pc cluster object to be used.
        **kwargs(dict):
          rpj_name_list(list): list of rpj names to monitor
          error_timeout(int): Error Timeout for RPJ.
        """
        self.session = pc_session

    def check_status(self) -> (None, bool):
        """
        Checks the task is in expected state or not
        Returns:
          True if in expected state else false
        """
        service = Service(self.session)
        status = service.get_oss_status()
        if status == service.ENABLED:
            return None, True
        else:
            return None, False
