import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.karbon.karbon_image import KarbonImage
from framework.helpers.rest_utils import RestAPIUtil

@pytest.fixture
def session():
    return MagicMock(spec=RestAPIUtil)

@pytest.fixture
def karbon_image(session):
    return KarbonImage(session)

class TestKarbonImage:
    def test_karbon_image_init(self, karbon_image):
        assert karbon_image.resource_type == "/acs/image"
        assert karbon_image.kind == "acs/image"
        assert karbon_image.session is not None

    @patch.object(KarbonImage, 'read', return_value=[])
    def test_list_images(self, mock_read, karbon_image):
        images = karbon_image.list()
        assert images == []
        mock_read.assert_called_once_with(endpoint="list")

    @patch.object(KarbonImage, 'create', return_value={"status": "success"})
    def test_download_image(self, mock_create, karbon_image):
        response = karbon_image.download(uuid="test-uuid")
        assert response == {"status": "success"}
        mock_create.assert_called_once_with(endpoint="download", data={"uuid": "test-uuid"})

    @patch.object(KarbonImage, 'read', return_value={"status": "COMPLETE"})
    def test_get_image_status(self, mock_read, karbon_image):
        status = karbon_image.get_image_status(image_uuid="test-uuid")
        assert status == {"status": "COMPLETE"}
        mock_read.assert_called_once_with(endpoint="download/test-uuid")
