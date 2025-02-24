
import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.pc_deployment_helper import PCDeploymentUtil
from framework.helpers.rest_utils import RestAPIUtil


class TestPCDeploymentUtil:
    @pytest.fixture
    def pc_deployment_util(self):
        self.pe_session = MagicMock(spec=RestAPIUtil)
        return PCDeploymentUtil(self.pe_session)

    def test_pc_deployment_util_init(self, pc_deployment_util):
        assert pc_deployment_util.pe_session == self.pe_session
        assert isinstance(pc_deployment_util, PCDeploymentUtil)
        

    def test_get_pcvm_size_spec(self, pc_deployment_util, mocker):
        pc_size = "small"
        expected_spec = {
            "num_sockets": 6,
            "memory_size_in_gb": 26,
            "data_disk_size_in_gb": 500
        }
        spec, error_message = pc_deployment_util.get_pcvm_size_spec(pc_size)
        assert spec == expected_spec
        assert error_message == ""
        
        pc_size = "invalid_size"
        spec, error_message = pc_deployment_util.get_pcvm_size_spec(pc_size)
        assert spec is None
        assert isinstance(error_message, Exception)
        assert "Failed to get VM Spec for PC Size" in str(error_message)
        
        MockPrismCentral = mocker.patch("framework.scripts.python.helpers.pc_deployment_helper.PrismCentral")
        mock_prism_central_instance = MockPrismCentral.return_value
        mock_prism_central_instance.create.return_value = {"task_uuid": "1234"}

        pc_config = {
        "pc_version": "5.8.1",
        "vm_name_list": ["PC-NameOption-1"],
        "ip_list": ["10.7.248.151"],
        "subnet_mask": "255.255.0.0",
        "default_gateway": "1.1.1.1",
        "container_uuid": "22492f23-16f1-4e10-8982-fe459097759d",
        "network_uuid": "690c7a3a-50b7-4b54-8080-35220323f674",
        "num_sockets": 4,
        "memory_size_in_gb": 16,
        "data_disk_size_in_gb": 500,
        "dns_server_ip_list": ["10.7.3.201"],
        "auto_register": False
        }
        task_uuid = pc_deployment_util.deploy_pc_vm(pc_config)
        assert task_uuid == "1234"
        mock_prism_central_instance.create.assert_called_once()

    def test_deploy_pc_vm(self, pc_deployment_util, mocker):
        pc_config = {
            "pc_version": "5.8.1",
            "vm_name_list": ["PC-NameOption-1"],
            "subnet_mask": "255.255.0.0",
            "default_gateway": "1.1.1.1",
            "container_uuid": "22492f23-16f1-4e10-8982-fe459097759d",
            "network_uuid": "690c7a3a-50b7-4b54-8080-35220323f674",
            "num_sockets": 4,
            "memory_size_in_gb": 16,
            "data_disk_size_in_gb": 500,
            "dns_server_ip_list": ["10.7.3.201"],
            "auto_register": False
        }

        with pytest.raises(IndexError):
            pc_deployment_util.deploy_pc_vm(pc_config)

        pc_config = {
            "pc_version": "5.8.1",
            "vm_name_list": ["PC-NameOption-1"],
            "ip_list": ["10.7.248.151"],
            "subnet_mask": "255.255.0.0",
            "default_gateway": "1.1.1.1",
            "container_uuid": "22492f23-16f1-4e10-8982-fe459097759d",
            "network_uuid": "690c7a3a-50b7-4b54-8080-35220323f674",
            "num_sockets": 4,
            "memory_size_in_gb": 16,
            "data_disk_size_in_gb": 500,
            "dns_server_ip_list": ["10.7.3.201"],
            "auto_register": False,
            "pc_vip": "1.1.1.10"
        }
        MockPrismCentral = mocker.patch("framework.scripts.python.helpers.pc_deployment_helper.PrismCentral")
        mock_prism_central_instance = MockPrismCentral.return_value
        mock_prism_central_instance.create.return_value = {"task_uuid": "1234"}

        task_uuid = pc_deployment_util.deploy_pc_vm(pc_config)
        assert task_uuid == "1234"
        mock_prism_central_instance.create.assert_called_once()
        payload = mock_prism_central_instance.create.call_args[1]['data']
        assert payload["resources"]["virtual_ip"] == "1.1.1.10"