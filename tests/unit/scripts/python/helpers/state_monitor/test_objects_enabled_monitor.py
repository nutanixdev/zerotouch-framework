import pytest 
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.service import Service
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from framework.scripts.python.helpers.state_monitor.objects_enabled_monitor import ObjectsEnabledMonitor

class TestObjectsEnabledMonitor:

    @pytest.fixture
    def pc_session(self):
        return MagicMock(spec=RestAPIUtil)

    @pytest.fixture
    def monitor(self, pc_session):
        return ObjectsEnabledMonitor(pc_session=pc_session)

    @patch.object(Service, 'get_oss_status')
    def test_check_status_enabled(self, mock_get_oss_status, monitor):
        # Mock the return value of the get_oss_status method
        mock_get_oss_status.return_value = Service.ENABLED
        
        _, status = monitor.check_status()
        assert status is True, "Expected status to be True when service is enabled."

    @patch.object(Service, 'get_oss_status')
    def test_check_status_not_enabled(self, mock_get_oss_status, monitor):
        # Mock the return value of the get_oss_status method
        mock_get_oss_status.return_value = "NOT_ENABLED"
        
        _, status = monitor.check_status()
        assert status is False, "Expected status to be False when service is not enabled."

    def test_init(self, monitor, pc_session):
        assert monitor.session == pc_session, "Expected session to be initialized correctly."

    def test_default_check_interval(self):
        assert ObjectsEnabledMonitor.DEFAULT_CHECK_INTERVAL_IN_SEC == 10, "Expected default check interval to be 10 seconds."

    def test_default_timeout(self):
        assert ObjectsEnabledMonitor.DEFAULT_TIMEOUT_IN_SEC == 1800, "Expected default timeout to be 1800 seconds."
