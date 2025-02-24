'''import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v3.service_group import ServiceGroup

class TestServiceGroup:

    @pytest.fixture
    def service_group(self):
        module = MagicMock()
        return ServiceGroup(module=module)

    def test_service_group_init(self, service_group):
        assert service_group.resource_type == "/service_groups"
        assert service_group.kind == "service_group"

    def test_get_uuid_by_name(self, service_group):
        service_group.list = MagicMock(return_value=[
            {"service_group": {"name": "test_service_group", "uuid": "test-uuid"}}
        ])

        uuid = service_group.get_uuid_by_name(entity_name="test_service_group")
       
        print(f"Returned UUID: {uuid}")
        print(f"Service group list call count: {service_group.list.call_count}")
        print(f"Service group list call args: {service_group.list.call_args}")
       
        assert uuid == "test-uuid"
        service_group.list.assert_called_once_with(filter="name==test_service_group")

    def test_create_service_group_spec(self, service_group):
        sg_info = {
            "name": "test_service_group",
            "description": "This is a test service group",
            "service_details": {
                "tcp": ["80", "443"],
                "udp": ["53"],
                "icmp": [{"type": 8, "code": 0}]
            }
        }

        spec = service_group.create_service_group_spec(sg_info)

        assert spec["name"] == "test_service_group"
        assert spec["description"] == "This is a test service group"
        assert {"protocol": "TCP", "tcp_port_range_list": [{"start_port": 80, "end_port": 80}, {"start_port": 443, "end_port": 443}]} in spec["service_list"]
        assert {"protocol": "UDP", "udp_port_range_list": [{"start_port": 53, "end_port": 53}]} in spec["service_list"]
        assert {"protocol": "ICMP", "icmp_type_code_list": [{"type": 8, "code": 0}]} in spec["service_list"]

    def test_build_spec_service_details(self, service_group):
        spec = service_group._get_default_spec()

        service_details = {
            "tcp": ["80", "443"],
            "udp": ["53"],
            "icmp": [{"type": 8, "code": 0}]
        }

        for protocol, values in service_details.items():
            spec, _ = service_group._build_spec_service_details(spec, {protocol: values})

        assert {"protocol": "TCP", "tcp_port_range_list": [{"start_port": 80, "end_port": 80}, {"start_port": 443, "end_port": 443}]} in spec["service_list"]
        assert {"protocol": "UDP", "udp_port_range_list": [{"start_port": 53, "end_port": 53}]} in spec["service_list"]
        assert {"protocol": "ICMP", "icmp_type_code_list": [{"type": 8, "code": 0}]} in spec["service_list"]

    def test_generate_port_range_list(self, service_group):
        port_config = ["80", "443", "1000-2000"]
        port_range_list = service_group.generate_port_range_list(port_config)

        expected = [
            {"start_port": 80, "end_port": 80},
            {"start_port": 443, "end_port": 443},
            {"start_port": 1000, "end_port": 2000}
        ]

        assert port_range_list == expected

        port_config = ["*"]
        port_range_list = service_group.generate_port_range_list(port_config)

        expected = [{"start_port": 0, "end_port": 65535}]

        assert port_range_list == expected'''

import pytest 
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.v3.service_group import ServiceGroup

class TestServiceGroup:

    @pytest.fixture
    def service_group(self):
        module = MagicMock()
        return ServiceGroup(module=module)

    def test_service_group_init(self, service_group):
        assert service_group.resource_type == "/service_groups"
        assert service_group.kind == "service_group"

    @patch.object(ServiceGroup, 'list')
    def test_get_uuid_by_name(self, mock_list, service_group):
        mock_list.return_value = [
            {"service_group": {"name": "test_service_group", "uuid": "test-uuid"}}
        ]

        uuid = service_group.get_uuid_by_name(entity_name="test_service_group")
        
        print(f"Returned UUID: {uuid}")
        print(f"Service group list call count: {mock_list.call_count}")
        print(f"Service group list call args: {mock_list.call_args}")

        mock_list.assert_called_once_with(filter="name==test_service_group")
        assert uuid == "test-uuid", f"Expected 'test-uuid', got {uuid}"

    def test_create_service_group_spec(self, service_group):
        sg_info = {
            "name": "test_service_group",
            "description": "This is a test service group",
            "service_details": {
                "tcp": ["80", "443"],
                "udp": ["53"],
                "icmp": [{"type": 8, "code": 0}]
            }
        }

        spec = service_group.create_service_group_spec(sg_info)

        assert spec["name"] == "test_service_group"
        assert spec["description"] == "This is a test service group"
        assert {"protocol": "TCP", "tcp_port_range_list": [{"start_port": 80, "end_port": 80}, {"start_port": 443, "end_port": 443}]} in spec["service_list"]
        assert {"protocol": "UDP", "udp_port_range_list": [{"start_port": 53, "end_port": 53}]} in spec["service_list"]
        assert {"protocol": "ICMP", "icmp_type_code_list": [{"type": 8, "code": 0}]} in spec["service_list"]

    def test_build_spec_service_details(self, service_group):
        spec = service_group._get_default_spec()

        service_details = {
            "tcp": ["80", "443"],
            "udp": ["53"],
            "icmp": [{"type": 8, "code": 0}]
        }

        for protocol, values in service_details.items():
            spec, _ = service_group._build_spec_service_details(spec, {protocol: values})

        assert {"protocol": "TCP", "tcp_port_range_list": [{"start_port": 80, "end_port": 80}, {"start_port": 443, "end_port": 443}]} in spec["service_list"]
        assert {"protocol": "UDP", "udp_port_range_list": [{"start_port": 53, "end_port": 53}]} in spec["service_list"]
        assert {"protocol": "ICMP", "icmp_type_code_list": [{"type": 8, "code": 0}]} in spec["service_list"]

    def test_generate_port_range_list(self, service_group):
        port_config = ["80", "443", "1000-2000"]
        port_range_list = service_group.generate_port_range_list(port_config)

        expected = [
            {"start_port": 80, "end_port": 80},
            {"start_port": 443, "end_port": 443},
            {"start_port": 1000, "end_port": 2000}
        ]

        assert port_range_list == expected

        port_config = ["*"]
        port_range_list = service_group.generate_port_range_list(port_config)

        expected = [{"start_port": 0, "end_port": 65535}]

        assert port_range_list == expected
