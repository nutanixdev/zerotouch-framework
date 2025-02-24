import pytest
import yaml
import json5 as json
import os
from unittest.mock import MagicMock, patch, mock_open
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from netaddr import IPNetwork
from cerberus import Validator
from distutils.file_util import copy_file
from framework.helpers.general_utils import *



@pytest.fixture
def sample_json():
    return '{"key": "value"}'

@pytest.fixture
def sample_yaml():
    return "key: value"

class TestUtils:

    @pytest.mark.parametrize("file_content, expected", [
        ('{"key": "value"}', {"key": "value"}),
        ('{"key": 123}', {"key": 123})
    ])
    def test_get_json_file_contents(self, mocker, file_content, expected):
        mocker.patch("builtins.open", mock_open(read_data=file_content))
        result = get_json_file_contents("dummy_path")
        assert result == expected

    @pytest.mark.parametrize("file_content, expected", [
        ("key: value", {"key": "value"}),
        ("num: 123", {"num": 123})
    ])
    def test_get_yml_file_contents(self, mocker, file_content, expected):
        mocker.patch("builtins.open", mock_open(read_data=file_content))
        result = get_yml_file_contents("dummy_path")
        assert result == expected

    @pytest.mark.parametrize("ip, expected", [
        ("192.168.1.1", True),
        ("999.999.999.999", False)
    ])
    def test_validate_ip(self, ip, expected):
        result = validate_ip("ip_field", ip, lambda f, e: None)
        assert result == expected

    @pytest.mark.parametrize("dsip, expected", [
        ("get-ip-from-ipam", True),
        ("192.168.1.1", True),
        ("999.999.999.999", False)
    ])
    def test_validate_dsip(self, dsip, expected):
        result = validate_dsip("ip_field", dsip, lambda f, e: None)
        assert result == expected

    
    @pytest.mark.parametrize("subnet, expected", [
        ("192.168.1.0/24", True),
        ("192.168.1.0/33", False)
    ])
    def test_validate_subnet(self, subnet, expected):
        result = validate_subnet("subnet_field", subnet, lambda f, e: None)
        assert result == expected

    @pytest.mark.parametrize("ip_list, expected", [
        (["192.168.1.1", "10.0.0.1"], True),
        (["192.168.1.1", "999.999.999.999"], False)
    ])
    def test_validate_ip_list(self, ip_list, expected):
        def error_func(field, error):
            raise ValueError(error)
        if expected:
            result = validate_ip_list("ip_field", ip_list, error_func)
            assert result is None
        else:
            with pytest.raises(ValueError):
                validate_ip_list("ip_field", ip_list, error_func)

    @pytest.mark.parametrize("string, expected", [
        ("no_spaces", False),
        ("has spaces", True)
    ])
    def test_contains_whitespace(self, string, expected):
        def error_func(field, error):
            raise ValueError(error)
        if expected:
           with pytest.raises(ValueError):
                contains_whitespace("field", string, error_func)
        else:
            result = contains_whitespace("field", string, error_func)
            assert result is None

    @pytest.mark.parametrize("domain, expected", [
        ("example.com", True),
        ("invalid_domain", False)
    ])
    def test_validate_domain(self, domain, expected):
        def error_func(field, error):
            raise ValueError(error)
        if expected:
            result = validate_domain("domain_field", domain, error_func)
            assert result is None
        else:
            with pytest.raises(ValueError):
                validate_domain("domain_field", domain, error_func)

    def test_validate_schema(self):
        schema = {"name": {"type": "string"}}
        data_valid = {"name": "test"}
        data_invalid = {"name": 123}
        assert validate_schema(schema, data_valid)
        assert not validate_schema(schema, data_invalid)

    def test_create_new_directory(self, mocker):
        mocker.patch("os.makedirs")
        create_new_directory("dummy_path")
        os.makedirs.assert_called_once_with("dummy_path", exist_ok=True)

    def test_delete_file_util(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.remove")
        delete_file_util("dummy_path")
        os.remove.assert_called_once_with("dummy_path")
    
    #test with valid files
    def test_copy_file_util(self, mocker):
        src_path = "/path/to/source/file.txt"
        dst_path = "/path/to/destination/file.txt"

        # Mock logger to verify if the correct log messages are logged
        mock_logger = mocker.patch("framework.helpers.general_utils.logger")

        # Mock copy_file function
        mock_copy_file = mocker.patch("framework.helpers.general_utils.copy_file")

        # Test case 1: Successful file copy
        copy_file_util(src_path, dst_path)
        mock_copy_file.assert_called_once_with(src_path, dst_path)
        mock_logger.info.assert_called_with(f"File '{dst_path}' copied successfully!")

        # Reset mocks for the next test
        mock_copy_file.reset_mock()
        mock_logger.reset_mock()

        # Test case 2: IOError during file copy
        mock_copy_file.side_effect = IOError("IO Error occurred")
        
        with pytest.raises(IOError):
            copy_file_util(src_path, dst_path)

        mock_copy_file.assert_called_once_with(src_path, dst_path)
        mock_logger.info.assert_called_with("IO error occurred while copying the file.")

        # Reset mocks for the next test
        mock_copy_file.reset_mock()
        mock_logger.reset_mock()

        # Test case 3: General Exception during file copy
        mock_copy_file.side_effect = Exception("General error occurred")

        with pytest.raises(Exception):
            copy_file_util(src_path, dst_path)

        mock_copy_file.assert_called_once_with(src_path, dst_path)
        mock_logger.error.assert_called_with("An error occurred while copying the file.")

    def test_run_script(self, mocker):
        mock_script = mocker.MagicMock()
        mock_script.return_value.run = MagicMock()
        run_script([mock_script], {"key": "value"})
        mock_script.return_value.run.assert_called_once()

    @pytest.mark.parametrize("first_obj, second_obj, expected", [
        ({"key1": "value1", "key2": "value2"}, {"key1": "value1"}, True),
        ({"key1": "value1", "key2": "value2"}, {"key1": "wrong_value"}, False)
    ])
    def test_intersection(self, first_obj, second_obj, expected):
        result = intersection(first_obj, second_obj)
        assert result == expected

    def test_enforce_data_arg(self):
        @enforce_data_arg
        def dummy_func(data, extra=None):
            return data

        assert dummy_func("test") == "test"

    @pytest.mark.parametrize("value, unit, expected", [
        (2, "MINUTE", (120, None)),
        (2, "INVALID", (None, "Invalid unit given for interval conversion to seconds"))
    ])
    def test_convert_to_secs(self, value, unit, expected):
        result = convert_to_secs(value, unit)
        assert result == expected

    @pytest.mark.parametrize("iterable, chunk_size, expected", [
        ([1, 2, 3, 4, 5], 2, [[1, 2], [3, 4], [5]]),
        ([1, 2, 3], 3, [[1, 2, 3]])
    ])
    def test_divide_chunks(self, iterable, chunk_size, expected):
        result = list(divide_chunks(iterable, chunk_size))
        assert result == expected
    
    def test_create_log_dir_push_logs(self, mocker):
        dir_to_create = "/path/to/dir"
        timestamp = "2024-10-04-12_00_00"
        data = {
            'project_root': '/path/to/project/root',
            'input_files': ['/path/to/input/config1.txt', '/path/to/input/config2.txt']
        }
        
        # Mocking dependencies
        mock_create_new_directory = mocker.patch("framework.helpers.general_utils.create_new_directory")
        mock_copy_file_util = mocker.patch("framework.helpers.general_utils.copy_file_util")
        mock_delete_file_util = mocker.patch("framework.helpers.general_utils.delete_file_util")
        mock_os_path_exists = mocker.patch("os.path.exists", return_value=True)
        mock_glob = mocker.patch("glob.glob")
        mock_os_path_join = mocker.patch("os.path.join", side_effect=lambda *args: "/".join(args))

        # Mock the return values for log and html file search
        mock_glob.side_effect = [
            ['/path/to/project/root/file1.log', '/path/to/project/root/file2.log'],  # for log files
            ['/path/to/project/root/file1.html', '/path/to/project/root/file2.html']  # for html files
        ]
        
        # Mock datetime.utcnow() for consistency in timestamp
        mock_datetime = mocker.patch("framework.helpers.general_utils.datetime")
        mock_datetime.utcnow.return_value.strftime.return_value = timestamp

        # Test case 1: Successful log, html, and config file handling
        create_log_dir_push_logs(dir_to_create, data)

        mock_create_new_directory.assert_any_call("/path/to/dir/logs")
        
        # Assert log files copy and delete
        mock_copy_file_util.assert_any_call("/path/to/project/root/file1.log", "/path/to/dir/logs/2024-10-04-12_00_00_file1.log")
        mock_copy_file_util.assert_any_call("/path/to/project/root/file2.log", "/path/to/dir/logs/2024-10-04-12_00_00_file2.log")
        mock_delete_file_util.assert_any_call("/path/to/project/root/file1.log")
        mock_delete_file_util.assert_any_call("/path/to/project/root/file2.log")
        
        # Assert HTML files copy and delete
        mock_copy_file_util.assert_any_call("/path/to/project/root/file1.html", "/path/to/dir/logs/2024-10-04-12_00_00_file1.html")
        mock_copy_file_util.assert_any_call("/path/to/project/root/file2.html", "/path/to/dir/logs/2024-10-04-12_00_00_file2.html")
        mock_delete_file_util.assert_any_call("/path/to/project/root/file1.html")
        mock_delete_file_util.assert_any_call("/path/to/project/root/file2.html")
        
        mock_create_new_directory.assert_any_call("/path/to/dir/configs")

        # Assert config files copy
        mock_copy_file_util.assert_any_call("/path/to/input/config1.txt", "/path/to/dir/configs/2024-10-04-12_00_00_config1.txt")
        mock_copy_file_util.assert_any_call("/path/to/input/config2.txt", "/path/to/dir/configs/2024-10-04-12_00_00_config2.txt")

        # Test case 2: Error while copying log file
        mock_copy_file_util.reset_mock()
        mock_copy_file_util.side_effect = [Exception("Error while copying log")]
        with pytest.raises(Exception):
            create_log_dir_push_logs(dir_to_create, data)

        # Ensure exception raised and delete_file_util still called
        mock_delete_file_util.assert_any_call("/path/to/project/root/file1.log")

        # Test case 3: Error while copying HTML file
        mock_copy_file_util.reset_mock()
        mock_delete_file_util.reset_mock()
        mock_copy_file_util.side_effect = [None, None, Exception("Error while copying HTML")]

        with pytest.raises(Exception):
            create_log_dir_push_logs(dir_to_create, data)

        # Ensure exception raised and delete_file_util still called

        # Test case 4: Error while copying config file
        mock_copy_file_util.reset_mock()
        mock_delete_file_util.reset_mock()
        mock_copy_file_util.side_effect = [None, None, None, None, Exception("Error while copying config")]

        with pytest.raises(Exception):
            create_log_dir_push_logs(dir_to_create, data)

    @pytest.mark.parametrize("subnet, expected", [
        ("192.168.1.0/24", "255.255.255.0"),
        ("10.0.0.0/8", "255.0.0.0")
    ])
    def test_get_subnet_mask(self, subnet, expected):
        result = get_subnet_mask(subnet)
        assert result == expected

    def test_send_mail_helper(self, mocker):
        mock_smtp = mocker.patch("smtplib.SMTP")
        send_mail_helper("subject", "body", "from@mail.com", "to@mail.com", "smtp_host")
        mock_smtp.return_value.sendmail.assert_called_once()
        mock_smtp.return_value.quit.assert_called_once()