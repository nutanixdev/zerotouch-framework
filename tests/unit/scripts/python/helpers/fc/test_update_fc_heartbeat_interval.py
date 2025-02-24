import pytest
from framework.scripts.python.helpers.fc.update_fc_heartbeat_interval import UpdateFCHeartbeatInterval
from framework.scripts.python.helpers.cvm.ssh_cvm import SSHCVM
from framework.scripts.python.script import Script
from unittest.mock import MagicMock, patch

class TestUpdateFcHeartbeatInterval:
    @pytest.fixture
    def update_fc_heartbeat_interval(self):
        return UpdateFCHeartbeatInterval(
            cvm_ip="test_ip", cvm_username="test_username", cvm_password="test_password",
            interval_min=10
            )
    
    def test_update_fc_heartbeat_interval_init(self, update_fc_heartbeat_interval):
        assert update_fc_heartbeat_interval.cvm_ip == "test_ip"
        assert update_fc_heartbeat_interval.interval_min == 10
        assert isinstance(update_fc_heartbeat_interval.ssh_cvm, SSHCVM)
        assert isinstance(update_fc_heartbeat_interval, UpdateFCHeartbeatInterval)
        assert isinstance(update_fc_heartbeat_interval, Script)
        
    def test_execute(self, update_fc_heartbeat_interval, mocker):
        mock_update_heartbeat_interval_mins = mocker.patch.object(SSHCVM, 'update_heartbeat_interval_mins')
        mock_update_heartbeat_interval_mins.return_value = (True, "test_error")
        update_fc_heartbeat_interval.execute()
        mock_update_heartbeat_interval_mins.assert_called_with(10)
        assert update_fc_heartbeat_interval.results == {"cvm_ip": "test_ip", "status": True, "error": "test_error"}
        
    def test_verify(self, update_fc_heartbeat_interval):
        pass