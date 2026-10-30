"""Prism Central task monitor implementation."""

import ntnx_prism_py_client
from ntnx_prism_py_client.models.prism.v4.config.TaskStatus import TaskStatus

from ztf.utils.utils import get_logger

from .state_monitor import StateMonitor, TaskNotFoundError

logger = get_logger(__name__)


class PcTaskMonitor(StateMonitor):
    """Polls a Prism Central task until it reaches a terminal state."""

    DEFAULT_CHECK_INTERVAL_IN_SEC = 5
    DEFAULT_TIMEOUT_IN_SEC = 600

    def __init__(
        self,
        api_client: ntnx_prism_py_client.api_client,
        ext_id: str,
        *,
        timeout_seconds: int | None = None,
        check_interval_seconds: int | None = None,
    ) -> None:
        """Create a task monitor.

        Args:
            api_client: The Prism Central API client.
            ext_id: Task extId to poll.
            timeout_seconds: Optional override for the 600 s default.
            check_interval_seconds: Optional override for the 5 s default.
        """
        super().__init__(
            timeout_seconds=timeout_seconds,
            check_interval_seconds=check_interval_seconds,
        )
        self.ext_id = ext_id
        self.task_api = ntnx_prism_py_client.TasksApi(api_client=api_client)
        self._logged_subtask_ids: set[str] = set()

    def check_status(self) -> tuple[bool, TaskStatus, dict]:
        """Fetch the current task status.

        Raises:
            TaskNotFoundError: If the task cannot be found or returns no
                data.  The caller should treat this as a hard failure
                (previously swallowed with a log line and then crashing
                on ``task_response.data``).

        Returns:
            ``(completed, status, response_data)`` tuple.
        """
        completed = False
        task_response = self.task_api.get_task_by_id(extId=self.ext_id)

        if not task_response or task_response.data is None:
            raise TaskNotFoundError(
                f"Task '{self.ext_id}' was not found or returned no data."
            )
        response_data = task_response.data
        status = response_data.status
        percent_complete = response_data.progress_percentage
        task_description = response_data.operation_description

        logger.info(f"Task description: {task_description}")
        logger.info(f"Task status: {status}, percent complete: {percent_complete}")
        self._log_populated_subtasks(response_data)

        if status in [
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.SUSPENDED,
        ]:
            completed = True

        return completed, status, response_data

    def _log_populated_subtasks(self, parent_task: object) -> None:
        """Log status for subtask refs present on the parent Task GET.

        ``Task.sub_tasks`` is a list of ``TaskReferenceInternal`` (ext_id
        only). GET returns a limited subset of children.

        TODO: If GET truncation hides children (``number_of_subtasks``
        greater than ``len(sub_tasks)``), list them with
        ``TasksApi.list_tasks(_filter="parentTask eq '<parent_ext_id>'")``.
        """
        subtasks = getattr(parent_task, "sub_tasks", None)
        number_of_subtasks = getattr(parent_task, "number_of_subtasks", None)
        if (
            isinstance(number_of_subtasks, int)
            and isinstance(subtasks, list)
            and number_of_subtasks > len(subtasks)
        ):
            logger.debug(
                "Task GET returned %s of %s subtask refs; listing is truncated.",
                len(subtasks),
                number_of_subtasks,
            )
        if not isinstance(subtasks, list):
            return
        for subtask in subtasks:
            self._log_one_subtask(getattr(subtask, "ext_id", None))

    def _log_one_subtask(self, subtask_ext_id: str | None) -> None:
        """Fetch and log one populated subtask; skip missing children.

        Child GET failures are swallowed so visibility logging cannot abort
        the parent wait. Each child is fetched once per monitor lifetime.
        """
        if not subtask_ext_id or subtask_ext_id in self._logged_subtask_ids:
            return
        self._logged_subtask_ids.add(subtask_ext_id)
        logger.debug(f"Subtask extId: {subtask_ext_id}")
        try:
            subtask_response = self.task_api.get_task_by_id(extId=subtask_ext_id)
        except Exception as exc:
            logger.debug(
                "Subtask '%s' status could not be fetched: %s",
                subtask_ext_id,
                exc,
            )
            return
        if not subtask_response or subtask_response.data is None:
            logger.debug(
                f"Subtask '{subtask_ext_id}' was not found or returned no data."
            )
            return
        subtask_data = subtask_response.data
        logger.info(
            f"Subtask status: {subtask_data.status}, "
            f"description: {subtask_data.operation_description}, "
            f"percent complete: {subtask_data.progress_percentage}"
        )
