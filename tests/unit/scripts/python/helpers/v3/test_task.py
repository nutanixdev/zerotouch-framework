import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v3.task import Task


@pytest.fixture
def task(mocker):
    session = mocker.MagicMock()
    return Task(session)


class TestTask:
    def test_task_init(self, task):
        assert task.resource_type == "/tasks"
        assert task.kind == "task"
        assert task.session is not None

    def test_poll(self, task, mocker):
        mock_create = mocker.patch.object(task, 'create', return_value={"status": "success"})

        response = task.poll(
            task_uuid_list=["uuid1", "uuid2"],
            poll_timeout_secs=30
        )

        assert response == {"status": "success"}
        payload = {
            "task_uuid_list": ["uuid1", "uuid2"],
            "poll_timeout_seconds": 30
        }
        mock_create.assert_called_once_with(data=payload, endpoint="poll", timeout=35)
