import pytest
from framework.scripts.python.helpers.state_monitor.fc_enabled_monitor import FcEnabledMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.genesis import Genesis
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from unittest.mock import MagicMock, patch

class TestFcEnabledMonitor:
    @pytest.fixture
    def fc_enabled_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return FcEnabledMonitor(session=self.session)
    
    def test_fc_enabled_monitor_init(self, fc_enabled_monitor):
        assert isinstance(fc_enabled_monitor, FcEnabledMonitor)
        assert isinstance(fc_enabled_monitor, StateMonitor)
        assert fc_enabled_monitor.session == self.session
    
    def test_check_status(self, fc_enabled_monitor, mocker):
        mock_genesis = mocker.patch.object(Genesis, 'is_fc_enabled')
        mock_genesis.return_value = (True, "test_status")
        assert fc_enabled_monitor.check_status() == (None, True)
        mock_genesis.return_value = False, "test_status"
        assert fc_enabled_monitor.check_status() == (None, False)