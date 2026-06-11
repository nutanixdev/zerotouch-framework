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

        if status in [
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELED,
            TaskStatus.SUSPENDED,
        ]:
            completed = True

        return completed, status, response_data
