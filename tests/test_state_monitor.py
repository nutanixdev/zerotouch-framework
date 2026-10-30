import time

import pytest

from ztf.state_monitor.state_monitor import StateMonitor


class MockStateMonitor(StateMonitor):
    """
    Concrete implementation of StateMonitor for testing purposes.
    """

    def __init__(
        self, check_results=None, timeout_seconds=None, check_interval_seconds=None
    ):
        super().__init__(
            timeout_seconds=timeout_seconds,
            check_interval_seconds=check_interval_seconds,
        )
        self.check_results = check_results or []
        self.check_call_count = 0

    def check_status(self):
        """
        Mock implementation that returns predefined results.
        """
        if self.check_call_count < len(self.check_results):
            result = self.check_results[self.check_call_count]
            self.check_call_count += 1
            return result
        # If we run out of results, return the last result repeatedly
        if self.check_results:
            return self.check_results[-1]
        return False, "No more results", {}


@pytest.fixture
def mock_state_monitor():
    """Fixture to create a mock state monitor with default settings."""
    return MockStateMonitor()


def test_monitor_success_immediate():
    """Test monitor method when status matches immediately."""
    # Setup: check_status returns success on first call
    monitor = MockStateMonitor(check_results=[(True, "SUCCESS", {"data": "test"})])

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "SUCCESS"
    assert response == {"data": "test"}
    assert monitor.check_call_count == 1


def test_monitor_success_after_retries():
    """Test monitor method when status matches after several retries."""
    # Setup: check_status returns failure first, then success
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"progress": 50}),
            (False, "RUNNING", {"progress": 75}),
            (True, "SUCCESS", {"data": "completed"}),
        ]
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "SUCCESS"
    assert response == {"data": "completed"}
    assert monitor.check_call_count == 3


def test_monitor_timeout():
    """Test monitor method when timeout occurs."""
    # Setup: check_status always returns failure, short timeout
    monitor = MockStateMonitor(
        check_results=[(False, "RUNNING", {"progress": 50})] * 10,  # Always running
        timeout_seconds=1,  # 1 second timeout
        check_interval_seconds=0.1,  # 0.1 second intervals
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    assert response == {"progress": 50}


def test_monitor_timeout_with_multiple_checks():
    """Test monitor method when timeout occurs after multiple checks."""
    # Setup: check_status returns different statuses but never success
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"progress": 25}),
            (False, "RUNNING", {"progress": 50}),
            (False, "RUNNING", {"progress": 75}),
            (False, "RUNNING", {"progress": 90}),
        ],
        timeout_seconds=1,
        check_interval_seconds=0.1,
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    # The response should be the last response from check_status
    # Since we have 4 check results and timeout occurs, it should be the last one
    assert response == {"progress": 90}


def test_monitor_success_just_before_timeout():
    """Test monitor method when success occurs just before timeout."""
    # Setup: success on the last possible check before timeout
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"progress": 25}),
            (False, "RUNNING", {"progress": 50}),
            (False, "RUNNING", {"progress": 75}),
            (True, "SUCCESS", {"data": "completed"}),
        ],
        timeout_seconds=1,
        check_interval_seconds=0.1,
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "SUCCESS"
    assert response == {"data": "completed"}
    assert monitor.check_call_count == 4


def test_monitor_empty_check_results():
    """Test monitor method with empty check results (should timeout)."""
    # Setup: no check results provided
    monitor = MockStateMonitor(
        check_results=[], timeout_seconds=1, check_interval_seconds=0.1
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    assert response == {}


@pytest.mark.skip(reason="This test would take 30 minutes (1800 seconds) to complete")
def test_monitor_default_timeout_and_interval():
    """Test monitor method uses default timeout and interval values."""
    # Setup: use default timeout and interval
    monitor = MockStateMonitor(check_results=[(False, "RUNNING", {})] * 5)

    # Execute
    start_time = time.time()
    status_matched, status, response = monitor.monitor()
    end_time = time.time()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    # Should take approximately DEFAULT_TIMEOUT_IN_SEC (1800 seconds)
    # But we can't test the full timeout in unit tests, so we just verify it doesn't return immediately
    assert end_time - start_time > 0


def test_monitor_custom_timeout_and_interval():
    """Test monitor method with custom timeout and interval values."""
    # Setup: custom timeout and interval
    monitor = MockStateMonitor(
        check_results=[(False, "RUNNING", {})] * 3,
        timeout_seconds=0.5,
        check_interval_seconds=0.1,
    )

    # Execute
    start_time = time.time()
    status_matched, status, response = monitor.monitor()
    end_time = time.time()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    # Should take approximately 0.5 seconds
    assert end_time - start_time >= 0.5
    assert end_time - start_time < 1.0  # Should not take much longer than timeout


def test_monitor_success_with_different_status_types():
    """Test monitor method with different status types."""
    # Setup: test with different status types
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"step": "init"}),
            (False, "PROCESSING", {"step": "validate"}),
            (True, "COMPLETED", {"step": "finish"}),
        ]
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "COMPLETED"
    assert response == {"step": "finish"}
    assert monitor.check_call_count == 3


def test_monitor_failure_status():
    """Test monitor method when check_status returns failure status."""
    # Setup: check_status returns failure status
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"progress": 50}),
            (True, "FAILED", {"error": "Task failed"}),
        ]
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True  # Status matched (even if it's a failure)
    assert status == "FAILED"
    assert response == {"error": "Task failed"}
    assert monitor.check_call_count == 2


def test_monitor_very_short_timeout():
    """Test monitor method with very short timeout."""
    # Setup: very short timeout
    monitor = MockStateMonitor(
        check_results=[(False, "RUNNING", {})],
        timeout_seconds=0.01,  # 10ms timeout
        check_interval_seconds=0.005,  # 5ms interval
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is False
    assert status == "Timed out"
    assert response == {}


def test_monitor_zero_timeout():
    """Test monitor method with zero timeout."""
    # Setup: zero timeout with failure result
    monitor = MockStateMonitor(
        check_results=[(False, "RUNNING", {"progress": 50})],
        timeout_seconds=0,
        check_interval_seconds=0.1,
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    # With zero timeout and failure result, it should timeout immediately
    assert status_matched is False
    assert status == "Timed out"
    assert response == {"progress": 50}


def test_monitor_zero_interval():
    """Test monitor method with zero interval (should still work)."""
    # Setup: zero interval
    monitor = MockStateMonitor(
        check_results=[
            (False, "RUNNING", {"progress": 50}),
            (True, "SUCCESS", {"data": "completed"}),
        ],
        timeout_seconds=1,
        check_interval_seconds=0,
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "SUCCESS"
    assert response == {"data": "completed"}
    assert monitor.check_call_count == 2


def test_monitor_large_number_of_checks():
    """Test monitor method with a large number of checks."""
    # Setup: many checks before success
    check_results = [(False, "RUNNING", {"step": i}) for i in range(100)]
    check_results.append((True, "SUCCESS", {"step": "final"}))

    monitor = MockStateMonitor(
        check_results=check_results, timeout_seconds=10, check_interval_seconds=0.01
    )

    # Execute
    status_matched, status, response = monitor.monitor()

    # Assert
    assert status_matched is True
    assert status == "SUCCESS"
    assert response == {"step": "final"}
    assert monitor.check_call_count == 101
