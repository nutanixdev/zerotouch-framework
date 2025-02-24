from typing import List
from framework.helpers.v4_api_client import ApiClientV4
import ntnx_prism_py_client

class Task:
    kind = "task"

    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "/tasks"
        self.client = v4_api_util.get_api_client("prism")
        self.tasks_api = ntnx_prism_py_client.TasksApi(
            api_client=self.client
            )

    def poll(self, task_uuid_list: List) -> List:
        """
        Call tasks/poll api to poll till the task_uuid is complete
        Args:
          task_uuid_list (list) : List of Task UUIDs to Poll

        Returns:
          Response
        """
        completed_tasks = []
        for task in task_uuid_list:
            task_response = self.tasks_api.get_task_by_id(task)
            if task_response.data.status not in ["RUNNING", "QUEUED"]:
              completed_tasks.append(task_response.to_dict()['data'])

        return completed_tasks

    # todo don't make other PcEntity methods available for Tasks
