from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.karbon.karbon_image import KarbonImage
from scripts.python.helpers.state_monitor.state_monitor import StateMonitor

logger = get_logger(__name__)


class KarbonImageDownloadMonitor(StateMonitor):
    """
    The class to wait for Karbon os image to be created
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 300

    def __init__(self, session: RestAPIUtil, image_uuid: str):
        """
        The constructor for TaskMonitor
        Args:
        session: request pc session to query the API
        """
        self.session = session
        self.uuid = image_uuid

    def check_status(self):
        """
        Checks the task is in expected state or not
        Returns:
          True if in expected state else false
        """
        status = False
        karbon_image = KarbonImage(self.session)

        # Only checking the image status, not the PC task
        response = karbon_image.get_image_status(self.uuid)

        if response.get("status") == KarbonImage.COMPLETE:
            status = True

        return response, status
