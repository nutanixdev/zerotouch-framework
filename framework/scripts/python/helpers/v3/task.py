from typing import List

from scripts.python.helpers.pc_entity import PcEntity
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Task(PcEntity):
    kind = "task"

    def __init__(self, session):
        self.resource_type = "/tasks"
        super(Task, self).__init__(session)

    def poll(self, task_uuid_list: List, poll_timeout_secs=30):
        """
        Call tasks/poll api to poll till the task_uuid is complete
        Args:
          task_uuid_list (list) : List of Task UUIDs to Poll
          poll_timeout_secs (int): Poll Timeout, default to 30 Secs

        Returns:
          Response
        """
        endpoint = "poll"

        payload = {
            "task_uuid_list": task_uuid_list,
            "poll_timeout_seconds": poll_timeout_secs
        }

        # Add 5 sec more for the Rest timeout, so that it doesn't bail
        # before task/poll returns
        return self.create(data=payload, endpoint=endpoint, timeout=poll_timeout_secs+5)

    # todo don't make other PcEntity methods available for Tasks
