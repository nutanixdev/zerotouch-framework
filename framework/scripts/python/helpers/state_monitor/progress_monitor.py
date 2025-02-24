from typing import List, Optional, Generator
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..v1.progress_monitor import ProgressMonitor

logger = get_logger(__name__)


class TaskMonitor(StateMonitor):
    """
    The class to wait for task status to come in expected state
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 600
    ABORTED = "aborted"
    CANCELED = "canceled"
    FAILED = "failed"
    QUEUED = "queued"
    RUNNING = "running"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    SUSPENDED = "suspended"

    def __init__(self, session: RestAPIUtil, **kwargs):
        """
        The constructor for TaskMonitor
        Args:
          kwargs:
            session: request pc or pe session to query the API
            task_uuid_list(list): uuids of tasks to monitor
        """
        self.session = session
        self.task_uuid_list = kwargs.get('task_uuid_list')
        self.completed_task_list = []
        self.failed_task_list = []
        self.progress_monitor = ProgressMonitor(self.session)

    @property
    def incomplete_task_list(self):
        return list(set(self.task_uuid_list) - set(self.completed_task_list))

    def check_status(self) -> (Optional[str], bool):
        """
        Checks the task is in expected state or not
        Returns:
          True if in expected state else false
        """
        logger.info("Total Tasks: {}".format(len(self.task_uuid_list)))
        logger.info("Completed Tasks: {}".format(len(self.completed_task_list)))

        completed = False
        response = None

        if not self.task_uuid_list:
            completed = True

        self.completed_task_list = []
        self.failed_task_list = []

        for subset_uuid_list in self.__uuid_list_chunks(self.incomplete_task_list):
            tasks = self.progress_monitor.poll(subset_uuid_list)
            for task in tasks:
                if task.get("status") in self.SUCCEEDED:
                    self.completed_task_list.append(task)
                elif task.get("status") in self.FAILED:
                    self.failed_task_list.append(f"{task.get('id')}-{task.get('errorDetail')}")

        if len(self.completed_task_list) == len(self.task_uuid_list):
            completed = True
        elif len(self.completed_task_list) + len(self.failed_task_list) == len(self.task_uuid_list):
            completed = True
            response = f"{self.failed_task_list}"

        logger.info("[{}/{}] Tasks Completed".format(len(self.completed_task_list),
                                                     len(self.task_uuid_list)))
        return response, completed

    @staticmethod
    def __uuid_list_chunks(uuid_list: List, chunk_size=100) -> Generator[List, None, None]:
        """
        Given list of uuid, return chunks of uuids
        Args:
          uuid_list (list): List of uuids
          chunk_size (int): Chunk size, default 100
        Returns:
          generator
        """
        for i in range(0, len(uuid_list), chunk_size):
            yield uuid_list[i:i + chunk_size]
