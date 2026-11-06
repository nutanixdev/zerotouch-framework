from unittest.mock import MagicMock

import pytest
from ntnx_prism_py_client.models.prism.v4.config.TaskStatus import TaskStatus

from ztf.state_monitor.state_monitor import TaskNotFoundError
from ztf.state_monitor.task_monitor import PcTaskMonitor


class DummyTaskResponse:
    class Data:
        def __init__(
            self,
            status,
            progress_percentage=100,
            operation_description="desc",
            sub_tasks=None,
            number_of_subtasks=None,
        ):
            self.status = status
            self.progress_percentage = progress_percentage
            self.operation_description = operation_description
            self.sub_tasks = sub_tasks
            self.number_of_subtasks = number_of_subtasks

    def __init__(self, status):
        self.data = self.Data(status)


def test_check_status_succeeded(monkeypatch):
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.return_value = DummyTaskResponse(TaskStatus.SUCCEEDED)
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid123")
    completed, status, response_data = monitor.check_status()
    assert completed is True
    assert status == TaskStatus.SUCCEEDED
    assert response_data.status == TaskStatus.SUCCEEDED


@pytest.mark.parametrize(
    "status", [TaskStatus.FAILED, TaskStatus.CANCELED, TaskStatus.SUSPENDED]
)
def test_check_status_terminal_states(monkeypatch, status):
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.return_value = DummyTaskResponse(status)
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid123")
    completed, got_status, response_data = monitor.check_status()
    assert completed is True
    assert got_status == status


def test_check_status_running(monkeypatch):
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.return_value = DummyTaskResponse(TaskStatus.RUNNING)
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid123")
    completed, status, response_data = monitor.check_status()
    assert completed is False
    assert status == TaskStatus.RUNNING


def test_check_status_not_found_raises_typed_error(monkeypatch):
    """Regression for 4.5: ``TaskNotFoundError`` replaces the silent
    ``logger.error + AttributeError`` path so callers can catch it."""
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.return_value = None
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid123")
    with pytest.raises(TaskNotFoundError, match="extid123"):
        monitor.check_status()


def test_check_status_missing_data_raises_typed_error(monkeypatch):
    """Regression for 4.5: response with ``data=None`` also raises
    ``TaskNotFoundError`` instead of falling through to the
    attribute-access crash."""
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    mock_response = MagicMock()
    mock_response.data = None
    mock_task_api.get_task_by_id.return_value = mock_response
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid123")
    with pytest.raises(TaskNotFoundError):
        monitor.check_status()


def test_configurable_timeout_and_interval(monkeypatch):
    """Regression for 4.4: per-instance overrides must flow through
    ``StateMonitor.__init__`` and reach ``monitor()``."""
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(
        mock_api_client,
        "extid-abc",
        timeout_seconds=42,
        check_interval_seconds=3,
    )
    assert monitor.timeout_seconds == 42
    assert monitor.check_interval_seconds == 3


def test_defaults_fall_back_to_class_values(monkeypatch):
    """Absent overrides fall back to ``DEFAULT_TIMEOUT_IN_SEC`` / interval."""
    mock_api_client = MagicMock()
    mock_task_api = MagicMock()
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )
    monitor = PcTaskMonitor(mock_api_client, "extid-abc")
    assert monitor.timeout_seconds == PcTaskMonitor.DEFAULT_TIMEOUT_IN_SEC
    assert monitor.check_interval_seconds == PcTaskMonitor.DEFAULT_CHECK_INTERVAL_IN_SEC


def _patch_task_api(monkeypatch, mock_task_api: MagicMock) -> None:
    monkeypatch.setattr(
        "ntnx_prism_py_client.TasksApi", lambda api_client: mock_task_api
    )


def test_check_status_logs_populated_subtasks(monkeypatch, caplog):
    """Subtask refs on the parent GET are fetched for visibility only."""
    parent = DummyTaskResponse(TaskStatus.RUNNING)
    parent.data.sub_tasks = [MagicMock(ext_id="child-ext")]
    child = DummyTaskResponse(TaskStatus.RUNNING)
    child.data.operation_description = "child op"
    child.data.progress_percentage = 40

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.side_effect = [parent, child]
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    with caplog.at_level("INFO"):
        completed, status, _ = monitor.check_status()

    assert completed is False
    assert status == TaskStatus.RUNNING
    assert mock_task_api.get_task_by_id.call_count == 2
    mock_task_api.get_task_by_id.assert_any_call(extId="child-ext")
    mock_task_api.list_tasks.assert_not_called()
    assert "child op" in caplog.text
    assert "percent complete: 40" in caplog.text


def test_check_status_skips_missing_populated_subtask(monkeypatch):
    """A missing child must not fail parent status polling."""
    parent = DummyTaskResponse(TaskStatus.RUNNING)
    parent.data.sub_tasks = [MagicMock(ext_id="missing-child")]

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.side_effect = [parent, None]
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    completed, status, _ = monitor.check_status()

    assert completed is False
    assert status == TaskStatus.RUNNING


def test_check_status_notes_truncated_subtask_list(monkeypatch, caplog):
    """GET may omit children; log when number_of_subtasks exceeds refs."""
    parent = DummyTaskResponse(TaskStatus.RUNNING)
    parent.data.sub_tasks = [MagicMock(ext_id="child-ext")]
    parent.data.number_of_subtasks = 5
    child = DummyTaskResponse(TaskStatus.RUNNING)

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.side_effect = [parent, child]
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    with caplog.at_level("DEBUG"):
        monitor.check_status()

    assert "returned 1 of 5 subtask refs" in caplog.text
    mock_task_api.list_tasks.assert_not_called()


def test_check_status_skips_subtask_without_ext_id(monkeypatch):
    """A ref with no ext_id is skipped instead of calling GET."""
    parent = DummyTaskResponse(TaskStatus.RUNNING)
    parent.data.sub_tasks = [MagicMock(ext_id=None)]

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.return_value = parent
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    monitor.check_status()

    mock_task_api.get_task_by_id.assert_called_once_with(extId="extid123")


def test_check_status_child_get_exception_does_not_fail_parent(monkeypatch):
    """A child GET error must not abort parent status polling.

    The parent task can still reach SUCCEEDED; visibility logging of
    children is best-effort.
    """
    parent = DummyTaskResponse(TaskStatus.SUCCEEDED)
    parent.data.sub_tasks = [MagicMock(ext_id="child-ext")]

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.side_effect = [parent, RuntimeError("boom")]
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    completed, status, _ = monitor.check_status()

    assert completed is True
    assert status == TaskStatus.SUCCEEDED


def test_check_status_does_not_refetch_same_subtask(monkeypatch):
    """Each child is GETted once per monitor lifetime."""
    parent = DummyTaskResponse(TaskStatus.RUNNING)
    parent.data.sub_tasks = [MagicMock(ext_id="child-ext")]
    child = DummyTaskResponse(TaskStatus.RUNNING)

    mock_task_api = MagicMock()
    mock_task_api.get_task_by_id.side_effect = [parent, child, parent]
    _patch_task_api(monkeypatch, mock_task_api)

    monitor = PcTaskMonitor(MagicMock(), "extid123")
    monitor.check_status()
    monitor.check_status()

    assert mock_task_api.get_task_by_id.call_count == 3
    assert mock_task_api.get_task_by_id.call_args_list[1].kwargs == {
        "extId": "child-ext"
    }
