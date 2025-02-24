import pytest
from framework.scripts.python import *
from framework.helpers.helper_functions import *
from unittest.mock import patch, MagicMock
from pathlib import Path
#from framework.helpers.log_utils import get_logger



logger = get_logger(__name__)

'''
    The following test cases are for the helper functions in helper_functions.py
    The functions are used to perform various tasks like getting file path, getting creds from vault, getting input data, validating input data,
    getting AOS URL mapping, getting hypervisor URL mapping, saving pod logs, saving logs, generating HTML from JSON, replacing config files,
    creating PC objects, creating PE objects, creating IPAM object, reading creds
'''
class TestHelperFunctions:
    
    @pytest.mark.parametrize("exists, file_name, file_path, should_raise_exception, expected_error_message", [
    (True, 'certificate', 'testfile.txt', False, None),
    (False, 'certificate', 'nonexistent.txt', True,
     'Could not find certificate details. Certificate details or password text file cannot be empty. Error is: '
     'Could not find .local_test/nonexistent.txt. Certificate details or password text file cannot be empty.')
    ])

    def test_get_file_path(self, mocker, exists, file_name, file_path, should_raise_exception, expected_error_message):

        mock_logger = mocker.patch('framework.helpers.helper_functions.logger')
        mock_sys_exit = mocker.patch('framework.helpers.helper_functions.sys.exit')
        mock_os_path_exists = mocker.patch('framework.helpers.helper_functions.os.path.exists')
        mock_os_path_exists.return_value = exists
        
        data = {"project_root": ".local_test"}
        if should_raise_exception:
            get_file_path(data, file_name, file_path)
            mock_sys_exit.assert_called_once()
            mock_logger.error.assert_called_once()
            args, _ = mock_logger.error.call_args
            print(args)
            assert expected_error_message == args[0]
        else:
            result = get_file_path(data, file_name, file_path)
            expected_path = os.path.join('.local_test', file_path)
            assert result == expected_path
            mock_sys_exit.assert_not_called()
            mock_logger.error.assert_not_called()
        
 
    def test_get_creds_from_vault(self, mocker):
        mock_get_file_path = mocker.patch('framework.helpers.helper_functions.get_file_path')
        mock_cyberark = mocker.patch('framework.helpers.helper_functions.CyberArk')
        data = {
            "vault_to_use": "cyberark",
            "vaults": {
                "cyberark": {
                    "metadata": {
                        "host": "test_host",
                        "port": 1234,
                        "crt_file": "test_crt_file",
                        "crt_key": "test_crt_key",
                        "user": "test_user",
                        "password_path": "test_password_path",
                        "appId": "test_appId",
                        "safe": "test_safe"
                    },
                    "credentials": {
                        "test_user_type": {
                            "username": "test_username",
                            "address": "test_address"
                        }
                    }
                }
            }
        }

        mock_get_file_path.side_effect = ["mock_cert", "mock_key", "mock_cert", "mock_key"]
        mock_cyberark_instance = MagicMock()
        mock_cyberark.return_value = mock_cyberark_instance
        mock_cyberark_instance.generate_auth_token.return_value = "mocked_auth_token"
        mock_cyberark_instance.fetch_creds.return_value = ("mocked_user", "mocked_password")
        mock_sleep = mocker.patch('framework.helpers.helper_functions.sleep')
        
        get_creds_from_vault(data)
        
        mock_cyberark_instance.fetch_creds.assert_called_once_with("test_username", "test_appId", "test_safe", "test_address", "AIMWebService")
        assert data["vaults"]["cyberark"]["credentials"]["test_user_type"]["username"] == "mocked_user"
        assert data["vaults"]["cyberark"]["credentials"]["test_user_type"]["password"] == "mocked_password"
        mock_sleep.assert_called_once_with(5)

        mock_cyberark_instance.fetch_creds.return_value = None
        mock_cyberark_instance.fetch_creds.side_effect = Exception("mocked_exception")
        mock_logger = mocker.patch('framework.helpers.helper_functions.logger')
        get_creds_from_vault(data)
        mock_logger.warning.assert_called_once()

        data["vault_to_use"] = None
        with pytest.raises(Exception , match="Kindly verify if you've selected the correct vault in 'vault_to_use'"):
            get_creds_from_vault(data)

    def test_get_input_data(self):
        project_root = Path(__file__).parents[3]
        data = {
            'project_root': project_root,
            'input_files' : [os.path.join(project_root, 'config/example-configs/script-configs/category_pc.yml')] #Choosing a random file to test
            }
        project_root = Path(__file__).parents[3]
        get_input_data(data)
        #Check if the given keys are present in the data
        print(data)
        assert any(key in data for key in ["vaults", "vault_to_use", "ipam", "ip_allocation_method", "pc_ip", "pc_credential"])

    def test_validate_input_data(self):
        data = {"schema": {}}
        result = validate_input_data(data)
        assert result is None

    def test_get_aos_url_mapping(self):
        data = {"imaging_parameters": {"aos_version": "5.20"}, "aos_versions": {"5.20": {"url": "https://test.com"}}}
        get_aos_url_mapping(data)
        assert "aos_url" in data

    def test_get_hypervisor_url_mapping(self):
        data = {
            "imaging_parameters": {
                "hypervisor_version": "6.7", "hypervisor_type": "ESXi"},
            "hypervisors": {"ESXi": {"ESXi": {"url": "https://test.com"}}}
            }
        #TODO : Clarify Code Logic for get_hypervisor_url_mapping
        get_hypervisor_url_mapping(data)
        assert "hypervisors" in data

    def test_save_pod_logs(self):
        data = {"pod": {"pod_name": "test-pod"}}
        with pytest.raises(Exception):
            save_pod_logs(data)

    def test_save_logs(self):
        with pytest.raises(Exception):
            save_logs({})

    def test_generate_html_from_json(self):
        data = {"json_output": {"key": "value"}}
        result = generate_html_from_json(data)
        assert result is None

    @pytest.mark.parametrize("os_path_exists", [True, False])
    @patch('os.path.exists')
    @patch('framework.helpers.helper_functions.copy_file_util')
    def test_replace_config_files(self, mock_copy_util, mock_os_path_exists, os_path_exists):
        project_root = Path(__file__).parents[3]
        data = {
            "project_root": project_root,
            "input_files": ["script-configs/category_pc.yml"]}
        
        mock_os_path_exists.return_value = os_path_exists
        mock_copy_util.return_value = None
        
        replace_config_files(data) #TODO : Clarify source and destination file paths
        
        mock_os_path_exists.assert_called_once()
        if os_path_exists:
            mock_copy_util.assert_called_once()
        else:
            mock_copy_util.assert_not_called()
                    
    def test_create_pc_objects(self):
        data = {
            "pc_ip": "10.1.1.1",
            "vaults": {"local": {"credentials": {"test": {"username": "admin", "password": "password"}}}},
            'vault_to_use': "local"
            }
        create_pc_objects(data)
        assert "pc_session" in data

    def test_create_pe_objects(self):
        data = {
            "clusters": {"10.1.1.110": {"name": "cluster-01"}},
            "vaults": {"local": {"credentials": {"test": {"username": "admin", "password": "password"}}}},
            "vault_to_use": "local"
            }
        create_pe_objects(data)
        assert "pe_session" in data["clusters"]["10.1.1.110"]

    @pytest.mark.parametrize("ip_allocation_method", ["static", "infoblox"])
    @patch('framework.helpers.helper_functions.read_creds')
    def test_create_ipam_object(self, mock_read_creds, ip_allocation_method):
        data = {
            "ipam": {
                "infoblox": {
                    "ipam_address": "infoblox.test.com",
                    "ipam_credential": "infoblox_user"
                }
            },
            "ip_allocation_method": ip_allocation_method  # static or infoblox
        }
        mock_read_creds.return_value = ("infoblox_user", "Ipam.123")
        create_ipam_object(data)
        if ip_allocation_method == "infoblox":
            assert "ipam_session" in data
        else:
            assert "ipam_session" not in data
            

    def test_read_creds(self):
        data = {"vault_to_use": "cyberark", "vaults": {"cyberark": {"credentials": {"test": {"username": "admin", "password": "password"}}}}}
        result = read_creds(data, credential="test")
        assert result == ("admin", "password")

