from typing import List
from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from scripts.python.helpers.v3.task import Task

logger = get_logger(__name__)


class PcTaskMonitor(StateMonitor):
    """
    The class to wait for task status to come in expected state
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 1800

    def __init__(self, session: RestAPIUtil, **kwargs):
        """
        The constructor for TaskMonitor
        Args:
          kwargs:
            session: request pc session to query the API
            expected_state(str): expected state of task
            task_uuid(str): uuid of task
        """
        self.session = session
        self.expected_state = kwargs.get('expected_state', 'SUCCEEDED')
        self.task_uuid_list = kwargs.get('task_uuid_list')
        self.completed_task_list = []
        self.failed_task_list = []
        self.task_op = Task(self.session)

    def check_status(self):
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
        for subset_uuid_list in self.__uuid_list_chunks(self.task_uuid_list):
            completed_tasks = self.task_op.poll(subset_uuid_list)
            for completed_task in completed_tasks:
                if completed_task.get("status") == "FAILED":
                    self.failed_task_list.append(completed_task)
                else:
                    self.completed_task_list.append(completed_tasks)

        if len(self.completed_task_list) == len(self.task_uuid_list):
            completed = True
        elif len(self.completed_task_list) + len(self.failed_task_list) == len(self.task_uuid_list):
            completed = True
            response = f"{self.failed_task_list}"

        logger.info("[{}/{}] Tasks Completed".format(len(self.completed_task_list),
                                                     len(self.task_uuid_list)))
        return response, completed

    @staticmethod
    def __uuid_list_chunks(uuid_list: List, chunk_size=100):
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
