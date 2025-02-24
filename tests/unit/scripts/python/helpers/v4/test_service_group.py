import pytest
from framework.scripts.python.helpers.v4.service_group import ServiceGroup

import ntnx_microseg_py_client.models.microseg.v4.config as v4MicrosegConfig

class TestServiceGroup:
    @pytest.fixture
    def service_group(self):
        return ServiceGroup()

    def test_service_group_init(self, service_group):
        assert service_group.resource_type == "microseg/v4.0.b1/config/service-groups"
        assert service_group.kind == "ServiceGroup"

    def test_get_uuid_by_name(self, mocker, service_group):
        mock_response = mocker.Mock()
        # Case1 : Found
        mock_response.data = [mocker.Mock(ext_id="12345")]
        mocker.patch.object(service_group.service_group_api, 'list_service_groups', return_value=mock_response)

        result = service_group.get_uuid_by_name("test_name")
        assert result == "12345"
        # Case2 : Not Found
        mock_response.data = []
        mocker.patch.object(service_group.service_group_api, 'list_service_groups', return_value=mock_response)

        result = service_group.get_uuid_by_name("test_name")
        assert result is None

    def test_list(self, mocker, service_group):
        mock_response_page_1 = mocker.Mock()
        from unittest.mock import PropertyMock
        mock_response_page_1.data = [
            mocker.Mock(),
            mocker.Mock()
        ]
        mock_response_page_1.data[0].name = "sg1"
        mock_response_page_1.data[1].name = "sg2"
        mock_response_page_2 = mocker.Mock()
        mock_response_page_2.data = [mocker.Mock()]
        mock_response_page_2.data[0].name = "sg3"
        mock_response_empty = mocker.Mock()
        mock_response_empty.data = []

        mocker.patch.object(service_group.service_group_api, 'list_service_groups', side_effect=[
            mock_response_page_1, mock_response_page_2, mock_response_empty
        ])

        result = service_group.list()
        assert len(result) == 3
        print(result)
        print(result[0])
        print((result[0]).name)
        assert result[0].name == "sg1"
        assert result[1].name == "sg2"
        assert result[2].name == "sg3"

        # Case2 : Empty
        mock_response_empty = mocker.Mock()
        mock_response_empty.data = []

        mocker.patch.object(service_group.service_group_api, 'list_service_groups', return_value=mock_response_empty)

        result = service_group.list()
        assert result == []

    def test_get_name_list(self, mocker, service_group):
        mock_response = mocker.Mock()
        mock_response.data = [mocker.Mock(), mocker.Mock()]
        mock_response.data[0].name = "sg1"
        mock_response.data[1].name = "sg2"
        mocker.patch.object(service_group, 'list', return_value=mock_response.data)

        result = service_group.get_name_list()
        assert result == ["sg1", "sg2"]

    def test_get_name_uuid_dict(self, mocker, service_group):
        mock_response = mocker.Mock()
        mock_response.data = [mocker.Mock(), mocker.Mock()]
        mock_response.data[0].name = "sg1"
        mock_response.data[0].ext_id = "123"
        mock_response.data[1].name = "sg2"
        mock_response.data[1].ext_id = "456"
        
        mocker.patch.object(service_group, 'list', return_value=mock_response.data)

        result = service_group.get_name_uuid_dict()
        assert result == {"sg1": "123", "sg2": "456"}

    def test_get_by_ext_id(self, mocker, service_group):
        mock_response = mocker.Mock()
        mocker.patch.object(service_group.service_group_api, 'get_service_group_by_id', return_value=mock_response)

        result = service_group.get_by_ext_id("12345")
        assert result == mock_response

    def test_delete_service_group_spec(self, mocker, service_group):
        mock_response = mocker.Mock()
        mock_response.data = mocker.Mock(ext_id="12345")
        mocker.patch.object(service_group, 'get_by_ext_id', return_value=mock_response)
        mocker.patch('framework.helpers.v4_api_client_cache_util.ApiClientV4.get_api_client', return_value=mocker.Mock(get_etag=mocker.Mock(return_value="etag_value")))

        result = service_group.delete_service_group_spec("12345")
        assert result == ("12345", "etag_value")

    def test_create_service_group_spec(self, mocker, service_group):
        sg_info = {
            "name": "test_sg",
            "description": "test_description",
            "service_details": {
                "tcp": ["80-90"],
                "udp": ["100-110"],
                "icmp": [{"type": 8, "code": 0}]
            }
        }
        mocker.patch.object(service_group, 'add_service_details')

        result = service_group.create_service_group_spec(sg_info)
        assert result.name == "test_sg"
        assert result.description == "test_description"
        service_group.add_service_details.assert_called_once_with(sg_info["service_details"], result)

    def test_update_service_group_spec(self, mocker, service_group):
        sg_info = {
            "name": "test_sg",
            "new_name": "new_test_sg",
            "description": "new_test_description",
            "service_details": {
                "tcp": ["80-90"],
                "udp": ["100-110"],
                "icmp": [{"type": 8, "code": 0}]
            }
        }
        service_group_obj = mocker.Mock(ext_id="123e4567-e89b-12d3-a456-426614174000")
        mocker.patch.object(service_group, 'add_service_details')
        mocker.patch('framework.helpers.v4_api_client_cache_util.ApiClientV4.get_api_client', return_value=mocker.Mock(get_etag=mocker.Mock(return_value="etag_value")))

        result, etag = service_group.update_service_group_spec(sg_info, service_group_obj)
        assert result.name == "new_test_sg"
        assert result.description == "new_test_description"
        assert result.ext_id == "123e4567-e89b-12d3-a456-426614174000"
        assert etag == "etag_value"
        service_group.add_service_details.assert_called_once_with(sg_info["service_details"], result)

    def test_add_service_details(self, service_group):
        service_details = {
            "tcp": ["80-90"],
            "udp": ["100-110"],
            "icmp": [{"type": 8, "code": 0}],
            "any_icmp": True
        }
        service_group_obj = v4MicrosegConfig.ServiceGroup.ServiceGroup()

        service_group.add_service_details(service_details, service_group_obj)

        assert len(service_group_obj.tcp_services) == 1
        assert service_group_obj.tcp_services[0].start_port == 80
        assert service_group_obj.tcp_services[0].end_port == 90

        assert len(service_group_obj.udp_services) == 1
        assert service_group_obj.udp_services[0].start_port == 100
        assert service_group_obj.udp_services[0].end_port == 110

        assert len(service_group_obj.icmp_services) == 1
        assert service_group_obj.icmp_services[0].is_all_allowed is True




