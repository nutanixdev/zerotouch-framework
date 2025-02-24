import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v4.task import Task

class TestTask:
    @pytest.fixture
    def task(self):
        return Task()

    def test_task_init(self, task):
        assert task.resource_type == "/tasks"

    def test_poll(self, task, mocker):
        mock_task_api = mocker.patch.object(task.tasks_api, 'get_task_by_id')
        
        mock_task_api.side_effect = [
            MagicMock(data=MagicMock(status="COMPLETED"), to_dict=lambda: {"data": {"id": "uuid1", "status": "COMPLETED"}}),
            MagicMock(data=MagicMock(status="FAILED"), to_dict=lambda: {"data": {"id": "uuid2", "status": "FAILED"}})
        ]

        response = task.poll(
            task_uuid_list=["uuid1", "uuid2"],
            poll_timeout_secs=30
        )

        assert response == [
            {"id": "uuid1", "status": "COMPLETED"},
            {"id": "uuid2", "status": "FAILED"}
        ]
        mock_task_api.assert_any_call("uuid1")
        mock_task_api.assert_any_call("uuid2")
