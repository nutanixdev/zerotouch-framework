"""Abstract base for polling-based status monitors (tasks, resources, etc.)."""

import time
from abc import ABC, abstractmethod
from typing import Any


class TaskNotFoundError(Exception):
    """Raised when a monitored task cannot be found by ext_id.

    Surfaces as a typed error instead of being swallowed by a silent
    ``logger.error(...)`` call followed by an ``AttributeError`` on
    ``task_response.data`` in the caller.
    """


class StateMonitor(ABC):
    """Abstract base class for polling-based state monitors."""

    #: Default timeout (seconds) used when the caller does not supply an
    #: override via the constructor or ``monitor()``.
    DEFAULT_TIMEOUT_IN_SEC = 1800
    #: Default polling interval (seconds) between ``check_status()`` calls.
    DEFAULT_CHECK_INTERVAL_IN_SEC = 5

    def __init__(
        self,
        *,
        timeout_seconds: int | None = None,
        check_interval_seconds: int | None = None,
    ) -> None:
        """Initialise with optional per-instance timeout overrides.

        Args:
            timeout_seconds: Override for ``DEFAULT_TIMEOUT_IN_SEC``.
                ``None`` falls back to the class default.
            check_interval_seconds: Override for the polling interval.
                ``None`` falls back to the class default.
        """
        self._timeout_seconds: int = (
            timeout_seconds
            if timeout_seconds is not None
            else self.DEFAULT_TIMEOUT_IN_SEC
        )
        self._check_interval_seconds: int = (
            check_interval_seconds
            if check_interval_seconds is not None
            else self.DEFAULT_CHECK_INTERVAL_IN_SEC
        )

    @property
    def timeout_seconds(self) -> int:
        """Effective timeout (seconds) for this monitor."""
        return self._timeout_seconds

    @property
    def check_interval_seconds(self) -> int:
        """Effective polling interval (seconds) for this monitor."""
        return self._check_interval_seconds

    def monitor(self) -> tuple[bool, str | None, dict[Any, Any]]:
        """Poll ``check_status`` until the target state is reached or timeout.

        No exceptions are raised on timeout: ``status`` is returned as
        ``"Timed out"`` so the caller can decide how to react.

        Returns:
            ``(status_matched, status, response)`` tuple.
        """
        start_time = time.time()
        status_matched = False
        response: dict[Any, Any] = {}
        status: str | None = None
        is_timeout = False

        while not is_timeout and not status_matched:
            status_matched, status, response = self.check_status()

            if not status_matched:
                time.sleep(self._check_interval_seconds)

            elapsed_time = time.time() - start_time
            if elapsed_time >= self._timeout_seconds:
                is_timeout = True

        if is_timeout:
            status = "Timed out"
        return status_matched, status, response

    @abstractmethod
    def check_status(self) -> tuple[bool, Any, dict[Any, Any]]:
        """Check the current status against the desired state.

        Subclasses must override.

        Returns:
            ``(matched, status, response)`` tuple where *matched* is
            ``True`` once the monitor can stop polling.
        """
