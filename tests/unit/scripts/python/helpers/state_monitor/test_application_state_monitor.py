import pytest
from framework.scripts.python.helpers.state_monitor.application_state_monitor import ApplicationStateMonitor
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from framework.scripts.python.helpers.v3.application import Application
from framework.helpers.rest_utils import RestAPIUtil
from unittest.mock import MagicMock

class TestApplicationStateMonitor:
    @pytest.fixture
    def application_state_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return ApplicationStateMonitor(
            session=self.session, expected_states="test_state",
            unexpected_states="test_unexpected_state", application_uuid="test_uuid"
            )

    def test_application_state_monitor_init(self, application_state_monitor):
        assert isinstance(application_state_monitor, ApplicationStateMonitor)
        assert isinstance(application_state_monitor, StateMonitor)
        assert application_state_monitor.session == self.session
        assert application_state_monitor._expected_states == "test_state"
        assert application_state_monitor._unexpected_states == "test_unexpected_state"
        assert application_state_monitor._application_uuid == "test_uuid"

    def test_check_status(self, application_state_monitor, mocker):
        mock_application = mocker.patch.object(Application, 'read')
        mock_application.return_value = {"status": {"state": "test_state"}}
        assert application_state_monitor.check_status() == ({"status": {"state": "test_state"}}, True)
        mock_application.return_value = {"status": {"state": "test_unexpected_state"}}
        assert application_state_monitor.check_status() == (None, True)
        mock_application.return_value = {"status": {"state": "test_state"}}
        assert application_state_monitor.check_status() == ({"status": {"state": "test_state"}}, True)
        mock_application.return_value = None
        assert application_state_monitor.check_status() == (None, False)
