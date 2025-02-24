import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.ipam.ipam import IPAM, IPMAMapping, Infoblox


class TestIPAM:
    @pytest.fixture
    def ipam(self):
        return IPAM(
            vendor="infoblox", ipam_address="test-address",
            username="test-user", password="test-password"
            )

    def test_ipam_init(self, mocker, ipam):
        assert isinstance(ipam, IPAM)
        assert isinstance(ipam.ipam_obj, Infoblox)
        
        with pytest.raises(Exception, match="Failed to create IPAM object. Error:"):
            error_ipam = IPAM(
                vendor="error", ipam_address="test-address",
                username="test-user", password="test-password" 
            )

    @patch.object(IPMAMapping.IPAM_VENDOR_MAPPING["infoblox"], 'create_host_record_with_next_available_ip')
    def test_create_host_record_with_next_available_ip(self, mock_create_host_record, ipam):
        network = "192.168.1.0/24"
        fqdn = "test.example.com"
        mock_create_host_record.return_value = ("192.168.1.2", None)
        ip_address, error = ipam.create_host_record_with_next_available_ip(network, fqdn)
        assert ip_address == "192.168.1.2"
        assert error is None
        mock_create_host_record.assert_called_once_with(network, fqdn, [])

    @patch.object(IPMAMapping.IPAM_VENDOR_MAPPING["infoblox"], 'check_host_record_exists')
    def test_check_host_record_exists(self, mock_check_host_record, ipam):
        ip = "192.168.1.1"
        mock_check_host_record.return_value = True
        exists = ipam.check_host_record_exists(ip)
        assert exists is True
        mock_check_host_record.assert_called_once_with(ip)

    @patch.object(IPMAMapping.IPAM_VENDOR_MAPPING["infoblox"], 'get_host_record')
    def test_get_host_record(self, mock_get_host_record, ipam):
        fqdn = "test.example.com"
        mock_get_host_record.return_value = [{"name": fqdn}]
        result = ipam.get_host_record(fqdn)
        assert result == [{"name": fqdn}]
        mock_get_host_record.assert_called_once_with(fqdn)

    @patch.object(IPMAMapping.IPAM_VENDOR_MAPPING["infoblox"], 'create_host_record')
    def test_create_host_record(self, mock_create_host_record, ipam):
        fqdn = "test.example.com"
        ip = "192.168.1.1"
        mock_create_host_record.return_value = (True, None)
        success, error = ipam.create_host_record(fqdn, ip)
        assert success is True
        assert error is None
        mock_create_host_record.assert_called_once_with(fqdn, ip)