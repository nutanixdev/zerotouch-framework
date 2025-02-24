import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.progress_monitor import ProgressMonitor
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestProgressMonitor:
    @pytest.fixture
    def progress_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return ProgressMonitor(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_progress_monitor_init(self, progress_monitor):
        assert progress_monitor.resource_type == "/progress_monitors"
        assert progress_monitor.session == self.session
        assert progress_monitor.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(progress_monitor, ProgressMonitor)
        assert isinstance(progress_monitor, PeEntityV1)
    
    def test_get_progress_monitors(self, mocker, progress_monitor):
        start_time = 1234567890
        query = {
            "hasSubTaskDetail": False,
            "count": 500,
            "page": 1,
            "filterCriteria": f"internal_task==false;(status==kSucceeded);last_updated_time_usecs=gt={start_time}"
        }
        
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value={
            "value": '{"progress_monitors": [{"progress": 100, "status": "kSucceeded"}]}'})
        result = progress_monitor.get_progress_monitors(start_time)
        mock_read.assert_called_once_with(query=query)
        assert result == {"value": '{"progress_monitors": [{"progress": 100, "status": "kSucceeded"}]}'}
