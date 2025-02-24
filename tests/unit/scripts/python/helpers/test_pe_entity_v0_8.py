import pytest

from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pe_entity_v0_8 import PeEntityV0_8
from framework.scripts.python.helpers.entity import Entity


class TestPeEntityV0_8:
    
    @pytest.fixture
    def pe_entity_v0_8(self):
        self.mock_session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "12345"
        return PeEntityV0_8(session=self.mock_session, proxy_cluster_uuid=self.proxy_cluster_uuid)

    def test_pe_entity_v0_8_init(self, pe_entity_v0_8):
        '''
        Test that the PeEntityV0_8 class is an instance of Entity and that the session and
        proxy_cluster_uuid attributes are set correctly
        '''
        assert isinstance(pe_entity_v0_8, PeEntityV0_8)
        assert isinstance(pe_entity_v0_8, Entity)
        assert pe_entity_v0_8.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert pe_entity_v0_8.session == self.mock_session
        
    def test_get_proxy_endpoint_with_cluster_uuid(self, pe_entity_v0_8):
        endpoint = "api/nutanix/v1/test"
        expected_endpoint = f"{endpoint}?proxyClusterUuid={self.proxy_cluster_uuid}"
        
        actual_endpoint = pe_entity_v0_8.get_proxy_endpoint(endpoint)
        assert actual_endpoint == expected_endpoint

    def test_get_proxy_endpoint_without_cluster_uuid(self, pe_entity_v0_8):
        pe_entity_v0_8.proxy_cluster_uuid=None
        endpoint = "/api/nutanix/v1/test"
        actual_endpoint = pe_entity_v0_8.get_proxy_endpoint(endpoint)
        assert actual_endpoint == endpoint

    def test_get_proxy_endpoint_with_existing_query(self, pe_entity_v0_8):
        endpoint = "/api/nutanix/v1/test?existingParam=param"
        expected_endpoint = f"{endpoint}&proxyClusterUuid={self.proxy_cluster_uuid}"
        actual_endpoint = pe_entity_v0_8.get_proxy_endpoint(endpoint)
        assert actual_endpoint == expected_endpoint

    @patch.object(Entity, "read")
    def test_read(self, mock_read, pe_entity_v0_8):
        endpoint = "test"
        expected_endpoint = f"{endpoint}?proxyClusterUuid={self.proxy_cluster_uuid}"
        pe_entity_v0_8.read(endpoint=endpoint)
        mock_read.assert_called_once_with(endpoint=expected_endpoint)
    
    @patch.object(Entity, "create")
    def test_create(self, mock_create, pe_entity_v0_8):
        endpoint = "test"
        expected_endpoint = f"{endpoint}?proxyClusterUuid={pe_entity_v0_8.proxy_cluster_uuid}"
        payload = {"name": "test"}
        pe_entity_v0_8.create(data=payload, endpoint=endpoint)
        mock_create.assert_called_once_with(data=payload, endpoint=expected_endpoint)
        
    @patch.object(Entity, "update")
    def test_update(self, mock_update, pe_entity_v0_8):
        endpoint = "test"
        expected_endpoint = f"{endpoint}?proxyClusterUuid={pe_entity_v0_8.proxy_cluster_uuid}"
        payload = {"name": "updated test"}
        pe_entity_v0_8.update(data=payload, endpoint=endpoint)
        mock_update.assert_called_once_with(data=payload, endpoint=expected_endpoint)

