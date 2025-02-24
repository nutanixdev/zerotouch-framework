import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v4.address_group import AddressGroup
from unittest.mock import MagicMock, patch

class TestAddressGroup:
    @pytest.fixture
    def address_group(self):
        with patch('framework.scripts.python.helpers.v4.address_group.ApiClientV4.get_api_client') as mock_get_api_client:
            mock_client = MagicMock()
            mock_get_api_client.return_value = mock_client
            yield AddressGroup()

    def test_address_group_init(self, address_group):
        assert address_group.resource_type == "microseg/v4.0.b1/config/address-groups"
        assert address_group.kind == "AddressGroup"

    def test_list(self, address_group):
        mock_response = MagicMock()
        mock_response.to_dict.return_value = {"data": []}
        address_group.address_group_api.list_address_groups = MagicMock()
        address_group.address_group_api.list_address_groups.return_value = mock_response
        result = address_group.list()
        assert result == {"data": []}

    def test_get_name_list(self, address_group):
        mock_response = {"data": [{"name": "test1"}, {"name": "test2"}]}
        address_group.list = MagicMock(return_value=mock_response)
        result = address_group.get_name_list()
        assert result == ["test1", "test2"]

    def test_get_uuid_by_name(self, address_group):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(ext_id="uuid1")]
        address_group.address_group_api.list_address_groups = MagicMock()
        address_group.address_group_api.list_address_groups.return_value = mock_response
        result = address_group.get_uuid_by_name("test")
        assert result == "uuid1"

    def test_get_name_uuid_dict(self, address_group):
        mock_response = {"data": [{"name": "test1", "ext_id": "uuid1"}, {"name": "test2", "ext_id": "uuid2"}]}
        address_group.list = MagicMock(return_value=mock_response)
        result = address_group.get_name_uuid_dict()
        assert result == {"test1": "uuid1", "test2": "uuid2"}

    def test_get_by_ext_id(self, address_group):
        mock_response = MagicMock()
        address_group.address_group_api.get_address_group_by_id = MagicMock()
        address_group.address_group_api.get_address_group_by_id.return_value = mock_response
        result = address_group.get_by_ext_id("uuid1")
        assert result == mock_response

    def test_delete_address_group_spec(self, address_group):
        mock_ag_obj = MagicMock()
        mock_ag_obj.data.ext_id = "uuid1"
        address_group.get_by_ext_id = MagicMock(return_value=mock_ag_obj)
        with patch('framework.scripts.python.helpers.v4.address_group.ApiClientV4.get_api_client') as mock_get_api_client:
            mock_client = MagicMock()
            mock_client.get_etag.return_value = "etag1"
            mock_get_api_client.return_value = mock_client
            result = address_group.delete_address_group_spec("uuid1")
            assert result == ("uuid1", "etag1")

    def test_create_address_group_spec(self, address_group):
        ag_info = {
            "name": "test",
            "description": "test description",
            "subnets": [{"network_ip": "192.168.1.0", "network_prefix": 24}],
            "ranges": [{"start_ip": "192.168.1.1", "end_ip": "192.168.1.10"}]
        }
        result = address_group.create_address_group_spec(ag_info)
        assert result.name == "test"
        assert result.description == "test description"
        assert len(result.ipv4_addresses) == 1
        assert len(result.ip_ranges) == 1

    def test_update_address_group_spec(self, address_group):
        ag_info = {
            "new_name": "new_test",
            "description": "new description",
            "subnets": [{"network_ip": "192.168.1.0", "network_prefix": 24}],
            "ranges": [{"start_ip": "192.168.1.1", "end_ip": "192.168.1.10"}]
        }
        ag_obj = MagicMock()
        with patch('framework.scripts.python.helpers.v4.address_group.ApiClientV4.get_api_client') as mock_get_api_client:
            mock_client = MagicMock()
            mock_client.get_etag.return_value = "etag1"
            mock_get_api_client.return_value = mock_client
            result, etag = address_group.update_address_group_spec(ag_info, ag_obj)
            assert result.name == "new_test"
            assert result.description == "new description"
            assert len(result.ipv4_addresses) == 1
            assert len(result.ip_ranges) == 1
            assert etag == "etag1"
