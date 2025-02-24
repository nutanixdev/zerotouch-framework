import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.state_monitor.objectstore_monitor import ObjectstoreMonitor
from framework.scripts.python.helpers.objects.objectstore import ObjectStore
from framework.helpers.rest_utils import RestAPIUtil

class TestObjectstoreMonitor:
    @pytest.fixture
    def monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return ObjectstoreMonitor(session=self.session, os_name="dummy_os")

    def test_init(self, monitor):
        assert monitor.session == self.session
        assert monitor.os_name == "dummy_os"
        assert monitor.progress_states == ['PENDING', 'SCALING_OUT', 'REPLACING_CERT', 'DELETING_INPUT']

    def test_check_status(self, mocker, monitor):
        mock_list = mocker.patch.object(ObjectStore, 'list')
        # Mock the return value of the list method
        mock_list.return_value = [{"name": "dummy_os", "state": "COMPLETE"}]
        
        response, status = monitor.check_status()
        assert status is True, "Expected status to be True when objectstore is not in progress."
        assert response.get("dummy_os") == "COMPLETE", "Expected objectstore state to be COMPLETE."
        
        mock_list.return_value = [{"name": "dummy_os", "state": "PENDING"}]
        
        response, status = monitor.check_status()
        assert status is False, "Expected status to be False when objectstore is in progress."
        assert response.get("dummy_os") == "PENDING", "Expected objectstore state to be PENDING."

    def test_default_check_interval(self):
        assert ObjectstoreMonitor.DEFAULT_CHECK_INTERVAL_IN_SEC == 60, "Expected default check interval to be 60 seconds."

    def test_default_timeout(self):
        assert ObjectstoreMonitor.DEFAULT_TIMEOUT_IN_SEC == 3600, "Expected default timeout to be 3600 seconds."