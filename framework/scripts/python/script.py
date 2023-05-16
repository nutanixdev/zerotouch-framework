import threading
from abc import abstractmethod, ABC
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Script(ABC):
    def __init__(self):
        self.name = type(self).__name__
        self.exceptions = []
        self.num_total_scripts = 0
        self.num_passed_scripts = 0
        self.pass_rate = 0.0

    def run(self, **kwargs):
        current_thread = threading.current_thread()

        if current_thread != threading.main_thread():
            current_thread_name = current_thread.name.split("-")[-1]
            current_thread.name = f"Thread-{current_thread_name}-{type(self).__name__}"

        self.execute(**kwargs)
        self.verify(**kwargs)

        if self.exceptions:
            for exception in self.exceptions:
                logger.error(f"{self.name}: {exception}")

        if self.num_total_scripts != 0:
            self.pass_rate = self.num_passed_scripts / self.num_total_scripts
        else:
            self.pass_rate = 100.0

        return self.pass_rate

    @abstractmethod
    def execute(self, **kwargs):
        pass

    @abstractmethod
    def verify(self, **kwargs):
        pass
