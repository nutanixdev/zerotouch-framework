import time

from helpers.log_utils import get_logger
from abc import abstractmethod, ABC

logger = get_logger(__name__)


class StateMonitor(ABC):
    """
    Abstract class for monitor.
    """
    DEFAULT_TIMEOUT_IN_SEC = 1800
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5

    def monitor(self, query_retries=True):
        """
        Keep waiting until target status is matched. No Exceptions will be raise
        when timed out, False is return instead. It is up to the caller to make
        decision about what to do when timed out.

        Args:
        query_retries(bool): False means monitor won't retry with timeout.

        Returns:
          bool: True if target status is matched, False otherwise.
        """
        start_time = time.time()
        status_matched = False
        response = {}
        elapsed_time = 0
        is_timeout = False

        logger.info("Started monitoring the state...")
        while not is_timeout and not status_matched:
            response, status_matched = self.check_status()
            if not query_retries:
                return status_matched

            if not status_matched:
                logger.info(f"Wait {self.DEFAULT_CHECK_INTERVAL_IN_SEC} seconds for the next check...")
                time.sleep(self.DEFAULT_CHECK_INTERVAL_IN_SEC)

            elapsed_time = time.time() - start_time
            if elapsed_time >= self.DEFAULT_TIMEOUT_IN_SEC:
                is_timeout = True

        if status_matched:
            logger.info(f"Completed {type(self).__name__} in duration: {elapsed_time:.2f} seconds")
            return response, True
        else:
            timeout_message = f"Timed out after {elapsed_time:.2f} seconds"
            logger.error(timeout_message)
            return None, False

    @abstractmethod
    def check_status(self):
        """
        Check the status is match the expected status or not. All the subclass
        must override this method
        """
        pass
