import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.genesis import Genesis
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from framework.scripts.python.helpers.state_monitor.karbon_enabled_monitor import KarbonEnabledMonitor

class TestKarbonEnabledMonitor:
    @pytest.fixture
    def karbon_enabled_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return KarbonEnabledMonitor(session=self.session)
    
    def test_init(self, karbon_enabled_monitor):
        assert karbon_enabled_monitor.session == self.session

    def test_default_check_interval(self, karbon_enabled_monitor, mocker):
        mock_genesis_enable_karbon = mocker.patch.object(Genesis, 'enable_karbon')
        mock_genesis_enable_karbon.return_value = ("True", True)
        status, _ = karbon_enabled_monitor.check_status()
        assert status == "True" and _ == True
        
    def test_default_check_interval(self, karbon_enabled_monitor):
        assert karbon_enabled_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC == 5

    def test_default_timeout(self, karbon_enabled_monitor):
        assert karbon_enabled_monitor.DEFAULT_TIMEOUT_IN_SEC == 300
