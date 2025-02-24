import pytest
from framework.scripts.python.helpers.state_monitor.blueprint_launch_monitor import BlueprintLaunchMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.blueprint import Blueprint
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from unittest.mock import MagicMock

class TestBlueprintLaunchMonitor:
    @pytest.fixture
    def blueprint_launch_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return BlueprintLaunchMonitor(
            session=self.session, expected_state="test_state",
            blueprint_uuid="test_uuid", request_id="test_request_id"
            )

    def test_blueprint_launch_monitor_init(self, blueprint_launch_monitor):
        assert isinstance(blueprint_launch_monitor, BlueprintLaunchMonitor)
        assert isinstance(blueprint_launch_monitor, StateMonitor)
        assert blueprint_launch_monitor.session == self.session
        assert blueprint_launch_monitor.expected_state == "test_state"
        assert blueprint_launch_monitor.blueprint_uuid == "test_uuid"
        assert blueprint_launch_monitor.request_id == "test_request_id"

    def test_check_status(self, blueprint_launch_monitor, mocker):
        mock_blueprint = mocker.patch.object(Blueprint, 'read')
        mock_blueprint.return_value = {"status": {"state": "test_state"}}
        assert blueprint_launch_monitor.check_status() == ({"status": {"state": "test_state"}}, True)
        mock_blueprint.return_value = {"status": {"state": "test_unexpected_state"}}
        assert blueprint_launch_monitor.check_status() == (None, False)
        mock_blueprint.return_value = {"status": {"state": "test_state"}}
        assert blueprint_launch_monitor.check_status() == ({"status": {"state": "test_state"}}, True)
        mock_blueprint.return_value = None
        assert blueprint_launch_monitor.check_status() == (None, False)