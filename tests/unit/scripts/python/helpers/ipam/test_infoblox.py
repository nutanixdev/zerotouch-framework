import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.ipam.infoblox import Infoblox
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.entity import Entity

class TestInfoblox:
    @pytest.fixture
    def infoblox(self):
        return Infoblox(address="test-address", username="test-user", password="test-password")

    def test_infoblox_init(self, infoblox):
        assert infoblox.resource == 'wapi/v2.12'
        assert isinstance(infoblox, Infoblox)
        assert isinstance(infoblox, Entity)

    @patch.object(Infoblox, 'read')
    def test_get_host_record(self, mock_read, infoblox):
        fqdn = "test.example.com"
        mock_read.return_value = [{"name": fqdn}]
        result = infoblox.get_host_record(fqdn)
        assert result == [{"name": fqdn}]
        mock_read.assert_called_once_with(endpoint=f"record:host?name={fqdn}")

    @patch.object(Infoblox, 'create')
    def test_create_host_record(self, mock_create, infoblox):
        fqdn = "test.example.com"
        ip = "192.168.1.1"
        mock_create.return_value = {"result": {"name": fqdn}}
        success, error = infoblox.create_host_record(fqdn, ip)
        assert success is True
        assert error is None
        payload = {"name": fqdn, "ipv4addrs": [{"ipv4addr": ip}]}
        mock_create.assert_called_once_with(endpoint="record:host?_return_as_object=1", data=payload)

    @patch.object(Infoblox, 'read')
    def test_check_host_record_exists(self, mock_read, infoblox):
        ip = "192.168.1.1"
        mock_read.return_value = [{"ipv4addr": ip}]
        exists = infoblox.check_host_record_exists(ip)
        assert exists is True
        mock_read.assert_called_once_with(endpoint=f"record:host?ipv4addr={ip}")

    @patch.object(Infoblox, 'create')
    @patch.object(Infoblox, 'get_host_record', return_value=[])
    def test_create_host_record_with_next_available_ip(self, mock_get_host_record, mock_create, infoblox):
        network = "192.168.1.0/24"
        fqdn = "test.example.com"
        mock_create.return_value = {
            "result": {
                "ipv4addrs": [{"ipv4addr": "192.168.1.2"}]
            }
        }
        ip_address, error = infoblox.create_host_record_with_next_available_ip(network, fqdn)
        assert ip_address == "192.168.1.2"
        assert error is None
        payload = {
            "name": fqdn,
            "ipv4addrs": [{
                "ipv4addr": {
                    "_object_function": "next_available_ip",
                    "_parameters": {"exclude": []},
                    "_result_field": "ips",
                    "_object": "network",
                    "_object_parameters": {"network": network}
                }
            }]
        }
        mock_create.assert_called_once_with(endpoint="record:host?_return_fields%2B=name,ipv4addrs&_return_as_object=1", data=payload)

