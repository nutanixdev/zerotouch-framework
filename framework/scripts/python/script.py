import threading
from abc import abstractmethod, ABC
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Script(ABC):
    def __init__(self, **kwargs):
        # If log_file is passed create a new logger and a file handler with the specified log file
        self.logger = get_logger(kwargs['log_file'], file_name=kwargs['log_file']) if kwargs.get('log_file') else None
        self.name = type(self).__name__
        self.results = {}
        self.exceptions = []

    def run(self, **kwargs):
        current_thread = threading.current_thread()

        if current_thread != threading.main_thread():
            current_thread_name = current_thread.name.split("-")[-1]
            current_thread.name = f"Thread-{current_thread_name}-{type(self).__name__}"

        self.execute(**kwargs)
        self.logger.info(f"Running Verification for the script '{type(self).__name__}'...")
        try:
            self.verify(**kwargs)
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}'")

        if self.exceptions:
            for exception in self.exceptions:
                self.logger.error(f"{self.name}: {exception}")

        return self.results

    @abstractmethod
    def execute(self, **kwargs):
        pass

    @abstractmethod
    def verify(self, **kwargs):
        pass
