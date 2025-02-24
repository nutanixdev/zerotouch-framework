import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pe_entity_v2 import PeEntityV2
from framework.scripts.python.helpers.entity import Entity

class TestPeEntityV2:
    @pytest.fixture
    def pe_entity_v2(self):
        self.mock_session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "12345"
        return PeEntityV2(session=self.mock_session, proxy_cluster_uuid=self.proxy_cluster_uuid)

    def test_pe_entity_v2_init(self, pe_entity_v2):
        '''
        Test that the PeEntityV1 class is an instance of Entity and that the session and proxy_cluster_uuid attributes are set correctly
        '''
        assert isinstance(pe_entity_v2, PeEntityV2)
        assert isinstance(pe_entity_v2, Entity)
        assert pe_entity_v2.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert pe_entity_v2.session == self.mock_session

    def test_get_proxy_endpoint_with_cluster_uuid(self, pe_entity_v2):
        pe_entity_v2.proxy_cluster_uuid="12345"
        endpoint = "/api/nutanix/v2.0/test"
        expected_endpoint = f"{endpoint}?proxyClusterUuid={pe_entity_v2.proxy_cluster_uuid}"
        actual_endpoint = pe_entity_v2.get_proxy_endpoint(endpoint)
        assert actual_endpoint == expected_endpoint

    def test_get_proxy_endpoint_without_cluster_uuid(self, pe_entity_v2):
        endpoint = "/api/nutanix/v2.0/test"
        actual_endpoint = pe_entity_v2.get_proxy_endpoint(endpoint)
        assert actual_endpoint == endpoint
    
    def test_get_proxy_endpoint_with_existing_query(self, pe_entity_v2):
        endpoint = "/api/nutanix/v2.0/test?existingParam=param"
        expected_endpoint = f"{endpoint}"
        actual_endpoint = pe_entity_v2.get_proxy_endpoint(endpoint)
        assert actual_endpoint == expected_endpoint

    @patch.object(Entity, "read")
    def test_read(self, mock_read, pe_entity_v2):
        endpoint = "test"
        pe_entity_v2.read(endpoint=endpoint)
        mock_read.assert_called_once_with(endpoint=endpoint)

    @patch.object(Entity, "create")
    def test_create(self, mock_create, pe_entity_v2):
        endpoint = "test"
        payload = {"name": "test"}
        pe_entity_v2.create(data=payload, endpoint=endpoint)
        mock_create.assert_called_once_with(data=payload, endpoint=endpoint)
        
    @patch.object(Entity, "update")
    def test_update(self, mock_update, pe_entity_v2):
        endpoint = "test"
        payload = {"name": "updated test"}
        pe_entity_v2.update(data=payload, endpoint=endpoint)
        mock_update.assert_called_once_with(data=payload, endpoint=endpoint)

    @patch.object(Entity, "read")
    def test_get_uuid(self, mock_read, pe_entity_v2):
        uuid = "12345"
        mock_read.return_value = {"uuid": uuid}
        actual_uuid = pe_entity_v2.get_uuid()
        assert actual_uuid == uuid
        mock_read.return_value = {}
        with pytest.raises(Exception) as excinfo:
            pe_entity_v2.get_uuid()
        assert "Could not fetch the UUID of the entity" in str(excinfo.value)

    #Maybe Include these cases for Entity class
    """def test_read_with_invalid_arguments(self, mocker, entity):
        mock_print = mocker.patch('builtins.print')
        with pytest.raises(TypeError):
            entity.read(12345)  # non-string argument

    def test_create_with_invalid_arguments(self, mocker, entity):
        mock_print = mocker.patch('builtins.print')
        with pytest.raises(TypeError):
            entity.create(12345)  # non-string argument

    def test_update_with_invalid_arguments(self, mocker, entity):
        mock_print = mocker.patch('builtins.print')
        with pytest.raises(TypeError):
            entity.update(12345) 

    def test_read_server_error(self, entity):
        entity.session.get.side_effect = Exception("Server error")
        with pytest.raises(Exception):
            entity.read(endpoint="/api/nutanix/v2.0/test")

    def test_create_server_error(self, entity):
        entity.session.post.side_effect = Exception("Server error")
        with pytest.raises(Exception):
            entity.create(endpoint="/api/nutanix/v2.0/test", data={"name": "test"})

    def test_update_server_error(self, entity):
        entity.session.put.side_effect = Exception("Server error")
        with pytest.raises(Exception):
            entity.update(endpoint="/api/nutanix/v2.0/test", data={"name": "test"})

    def test_get_uuid_server_error(self, entity):
        entity.session.get.side_effect = Exception("Server error")
        with pytest.raises(Exception):
            entity.get_uuid()"""
