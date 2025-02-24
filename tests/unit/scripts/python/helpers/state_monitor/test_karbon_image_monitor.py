import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.karbon.karbon_image import KarbonImage
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from framework.scripts.python.helpers.state_monitor.karbon_image_monitor import KarbonImageDownloadMonitor

class TestKarbonImageDownloadMonitor:

    @pytest.fixture
    def session(self):
        return MagicMock(spec=RestAPIUtil)

    @pytest.fixture
    def monitor(self, session):
        return KarbonImageDownloadMonitor(session=session, image_uuid="dummy_uuid")

    @patch.object(KarbonImage, 'get_image_status')
    def test_check_status_complete(self, mock_get_image_status, monitor):
        # Mock the return value of the get_image_status method
        mock_get_image_status.return_value = {"status": KarbonImage.COMPLETE}
       
        response, status = monitor.check_status()
        assert status is True, "Expected status to be True when image download is complete."
        assert response.get("status") == KarbonImage.COMPLETE, "Expected response status to be COMPLETE."

    @patch.object(KarbonImage, 'get_image_status')
    def test_check_status_not_complete(self, mock_get_image_status, monitor):
        # Mock the return value of the get_image_status method
        mock_get_image_status.return_value = {"status": "IN_PROGRESS"}
       
        response, status = monitor.check_status()
        assert status is False, "Expected status to be False when image download is not complete."
        assert response.get("status") == "IN_PROGRESS", "Expected response status to be IN_PROGRESS."

    def test_init(self, monitor, session):
        assert monitor.session == session, "Expected session to be initialized correctly."
        assert monitor.uuid == "dummy_uuid", "Expected UUID to be initialized correctly."

    def test_default_check_interval(self):
        assert KarbonImageDownloadMonitor.DEFAULT_CHECK_INTERVAL_IN_SEC == 30, "Expected default check interval to be 30 seconds."

    def test_default_timeout(self):
        assert KarbonImageDownloadMonitor.DEFAULT_TIMEOUT_IN_SEC == 1800, "Expected default timeout to be 1800 seconds."