import pytest
from framework.scripts.python.helpers.state_monitor.pc_register_monitor import PcRegisterMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from unittest.mock import MagicMock

class TestPcRegisterMonitor:
    @pytest.fixture
    def pc_register_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return PcRegisterMonitor(
            session=self.session, pe_uuids=["test_uuid1", "test_uuid2"],
            )
    
    def test_pc_register_monitor_init(self, pc_register_monitor):
        assert isinstance(pc_register_monitor, PcRegisterMonitor)
        assert isinstance(pc_register_monitor, StateMonitor)
        assert pc_register_monitor.session == self.session
        assert pc_register_monitor._pe_uuids == ["test_uuid1", "test_uuid2"]
    
    def test_check_status(self, pc_register_monitor, mocker):
        mock_pc = mocker.patch("framework.scripts.python.helpers.state_monitor.pc_register_monitor.PcCluster", autospec=True)
        
        mock_pc.return_value.name_uuid_map = {"test_name1": "test_uuid1", "test_name2": "test_uuid2"}
        pc_cluster_uuids, cluster_sync_complete = pc_register_monitor.check_status()
        assert list(pc_cluster_uuids) == ["test_uuid1", "test_uuid2"]
        assert cluster_sync_complete == True

        mock_pc.return_value.name_uuid_map = {}
        pc_cluster_uuids, cluster_sync_complete = pc_register_monitor.check_status()
        assert list(pc_cluster_uuids) == []
        assert cluster_sync_complete == False
        
        mock_pc.return_value.name_uuid_map = {"test_name1": "test_uuid1", "test_name2": "test_uuid3"}
        pc_cluster_uuids, cluster_sync_complete = pc_register_monitor.check_status()
        assert list(pc_cluster_uuids) == ["test_uuid1", "test_uuid3"]
        assert cluster_sync_complete == False
        