import pytest
from unittest.mock import MagicMock, patch
from copy import deepcopy
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.address_group import AddressGroup



class TestAddressGroup:

    @pytest.fixture
    def address_group(self):
        self.module = MagicMock(spec=RestAPIUtil)
        return AddressGroup(module=self.module)

    def test_address_group_init(self, address_group):
        '''
        Test that the AddressGroup class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert address_group.resource_type == "/address_groups"
        assert isinstance(address_group, AddressGroup)
        assert isinstance(address_group, PcEntity)

    def test_get_uuid_by_name(self, address_group, mocker):
        entity_name = "test_ag"
        response = [{"address_group": {"name": entity_name, "uuid": "1234"}}]
        mock_list = mocker.patch.object(PcEntity, 'list', return_value=response)

        print(f"Mocked response: {response}")

        # Simulate the extraction logic in the method
        uuid = None
        for entity in response:
            if entity.get("address_group", {}).get("name") == entity_name:
                uuid = entity.get("address_group", {}).get("uuid")
                break

        print(f"Manually extracted UUID: {uuid}")

        # Call the method to get the UUID
        uuid_method = address_group.get_uuid_by_name(entity_name=entity_name)

        print(f"Returned UUID from method: {uuid_method}")

        # Ensure the list method was called with the correct filter
        mock_list.assert_called_once_with(filter="name==test_ag")
        assert uuid_method == "1234"

    def test_create_address_group_spec(self, address_group):
        ag_info = {
            "name": "test_ag",
            "description": "Test description",
            "subnets": [
                {"network_ip": "192.168.1.0", "network_prefix": "24"}
            ]
        }
        spec = address_group.create_address_group_spec(ag_info)

        expected_spec = {
            "name": "test_ag",
            "description": "Test description",
            "ip_address_block_list": [
                {"ip": "192.168.1.0", "prefix_length": "24"}
            ]
        }
        assert spec == expected_spec

    def test_get_default_spec(self, address_group):
        default_spec = address_group._get_default_spec()
        expected_spec = {
            "name": None,
            "description": "",
            "ip_address_block_list": []
        }
        assert default_spec == expected_spec

    def test_build_spec_name(self):
        payload = {}
        AddressGroup._build_spec_name(payload, "test_name")
        assert payload["name"] == "test_name"

    def test_build_spec_desc(self):
        payload = {}
        AddressGroup._build_spec_desc(payload, "test_description")
        assert payload["description"] == "test_description"

    def test_build_spec_subnets(self, address_group):
        payload = {}
        subnets = [{"network_ip": "192.168.1.0", "network_prefix": "24"}]
        address_group._build_spec_subnets(payload, subnets)

        expected_payload = {
            "ip_address_block_list": [
                {"ip": "192.168.1.0", "prefix_length": "24"}
            ]
        }
        assert payload == expected_payload

    def test_get_ip_address_block(self):
        ip_block = AddressGroup._get_ip_address_block("192.168.1.0", "24")
        expected_block = {"ip": "192.168.1.0", "prefix_length": "24"}
        assert ip_block == expected_block

