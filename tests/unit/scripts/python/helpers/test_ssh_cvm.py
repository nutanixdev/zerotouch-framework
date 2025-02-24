import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.cvm.ssh_cvm import SSHCVM
from framework.scripts.python.helpers.ssh_entity import SSHEntity

class TestSSHCVM:
    @pytest.fixture
    def ssh_cvm(self):
        self.cvm_ip = "test_ip"
        self.cvm_username = "test_username"
        self.cvm_password = "test_password"
        return SSHCVM(
            cvm_ip=self.cvm_ip, cvm_username=self.cvm_username,
            cvm_password=self.cvm_password
        )
        
    def test_ssh_cvm_init(self, ssh_cvm):
        assert ssh_cvm.cvm_ip == self.cvm_ip
        assert ssh_cvm.cvm_username == self.cvm_username
        assert ssh_cvm.cvm_password == self.cvm_password
        assert isinstance(ssh_cvm, SSHCVM)
        assert isinstance(ssh_cvm, SSHEntity)
    
    def test_stop_foundation(self, mocker, ssh_cvm):
        mock_send_to_interactive_channel = mocker.patch.object(ssh_cvm, "send_to_interactive_channel")
        mock_receive_from_interactive_channel = mocker.patch.object(ssh_cvm, "receive_from_interactive_channel")
        mock_channel = MagicMock()
        mock_receive_from_interactive_channel.return_value = "response_data"
        
        result = ssh_cvm.stop_foundation(mock_channel)
        
        mock_send_to_interactive_channel.assert_called_once_with(mock_channel, "source /etc/profile; genesis stop foundation")
        mock_receive_from_interactive_channel.assert_called_once_with(mock_channel)
        mock_logger_error = mocker.patch.object(ssh_cvm.logger, "error")
        assert result == True
        
        mock_receive_from_interactive_channel.return_value = None
        mock_time = mocker.patch('time.time') # Mock time.time to skip time_to_wait
        mock_time.side_effect = [0, 121]
        result = ssh_cvm.stop_foundation(mock_channel)
        
        mock_send_to_interactive_channel.assert_called_with(mock_channel, "source /etc/profile; genesis stop foundation")
        mock_receive_from_interactive_channel.assert_called_with(mock_channel)
        mock_logger_error.assert_called_once_with("Waited for 2.0 mins, task not finished")
        assert result == False
    
    def test_restart_genesis(self, mocker, ssh_cvm):
        mock_send_to_interactive_channel = mocker.patch.object(ssh_cvm, "send_to_interactive_channel")
        mock_receive_from_interactive_channel = mocker.patch.object(ssh_cvm, "receive_from_interactive_channel")
        mock_channel = MagicMock()
        mock_receive_from_interactive_channel.return_value = "Genesis started on pids"
        mock_logger_error = mocker.patch.object(ssh_cvm.logger, "error")
        
        result = ssh_cvm.restart_genesis(mock_channel)
        
        mock_send_to_interactive_channel.assert_called_once_with(mock_channel, "source /etc/profile; genesis restart")
        mock_receive_from_interactive_channel.assert_called_once_with(mock_channel)
        assert result == True
        mock_receive_from_interactive_channel.return_value = None
        mock_time = mocker.patch('time.time') # Mock time.time to skip time_to_wait
        mock_time.side_effect = [0, 181]
        result = ssh_cvm.restart_genesis(mock_channel)
        mock_send_to_interactive_channel.assert_called_with(mock_channel, "source /etc/profile; genesis restart")
        mock_receive_from_interactive_channel.assert_called_with(mock_channel)
        mock_logger_error.assert_called_once_with("Waited for 3.0 mins, task not finished")
        assert result == None
    
    def test_update_heartbeat_interval_mins(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        update_file_command = "sed -r -i '/heartbeat_interval_mins/ s/(^.*)(:.*)/\\1: 1,/g' ~/foundation/config/foundation_settings.json"
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        mock_execute_command.return_value = "", "error"
        
        status,error_msg = ssh_cvm.update_heartbeat_interval_mins(interval_min=1)
        mock_execute_command.assert_called_once_with(
            mock_get_ssh_connection.return_value, update_file_command)
        assert error_msg == "test_ip - Error Updating heartbeat interval mins: error" and status == False
        
        mock_execute_command.return_value = "", "No such file or directory"
        mock_sleep = mocker.patch('time.sleep') # Mock time.sleep to skip time_to_wait
        status,error_msg = ssh_cvm.update_heartbeat_interval_mins(interval_min=1)
        for i in range(20): # 20 retries with 5 seconds sleep
            mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, update_file_command)
        assert error_msg == f"test_ip - Error Updating heartbeat interval mins: No such file or directory" and status == False
        
        mock_execute_command.return_value = "", None
        mock_get_interactive_shell = mocker.patch.object(ssh_cvm, "get_interactive_shell")
        mock_stop_foundation = mocker.patch.object(ssh_cvm, "stop_foundation")
        mock_restart_genesis = mocker.patch.object(ssh_cvm, "restart_genesis")
        
        mock_stop_foundation.return_value = True
        mock_restart_genesis.return_value = False
        status,error_msg = ssh_cvm.update_heartbeat_interval_mins(interval_min=1)
        mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, update_file_command)
        mock_get_interactive_shell.assert_called_once_with(mock_get_ssh_connection.return_value)
        mock_stop_foundation.assert_called_once_with(mock_get_interactive_shell.return_value)
        mock_restart_genesis.assert_called_once_with(mock_get_interactive_shell.return_value)
        assert status == False and error_msg == "test_ip: Failed to restart genesis"
        
        mock_restart_genesis.return_value = True
        status,error_msg = ssh_cvm.update_heartbeat_interval_mins(interval_min=1)
        mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, update_file_command)
        mock_get_interactive_shell.assert_called_with(mock_get_ssh_connection.return_value)
        mock_stop_foundation.assert_called_with(mock_get_interactive_shell.return_value)
        mock_restart_genesis.assert_called_with(mock_get_interactive_shell.return_value)
        assert status == True and error_msg == None

        mock_stop_foundation.return_value = False
        status,error_msg = ssh_cvm.update_heartbeat_interval_mins(interval_min=1)
        mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, update_file_command)
        mock_get_interactive_shell.assert_called_with(mock_get_ssh_connection.return_value)
        mock_stop_foundation.assert_called_with(mock_get_interactive_shell.return_value)
        assert status == False and error_msg == "test_ip: Failed to stop foundation"


    def test_enable_one_node(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        mock_get_interactive_shell = mocker.patch.object(ssh_cvm, "get_interactive_shell")
        mock_stop_foundation = mocker.patch.object(ssh_cvm, "stop_foundation")
        mock_restart_genesis = mocker.patch.object(ssh_cvm, "restart_genesis")
        mock_close_ssh_connection = mocker.patch.object(ssh_cvm, "close_ssh_connection")
        
        mock_execute_command.return_value = ("one_node", None)
        status,error_msg = ssh_cvm.enable_one_node()
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            mock_get_ssh_connection.return_value, "source /etc/profile; cat /etc/nutanix/hardware_config.json | grep one_node")
        mock_close_ssh_connection.assert_called_once_with(mock_get_ssh_connection.return_value)
        assert status == False and error_msg == None

        mock_execute_command.return_value = (None, "error")
        status,error_msg = ssh_cvm.enable_one_node()
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, "source /etc/profile; cat /etc/nutanix/hardware_config.json | grep one_node")
        mock_close_ssh_connection.assert_called_with(mock_get_ssh_connection.return_value)
        assert status == False and error_msg == "error"
        
        mock_sleep = mocker.patch('time.sleep')
        mock_execute_command.return_value = (None, None)
        status,error_msg = ssh_cvm.enable_one_node()
        sed_command = 's/"hardware_attributes": {/"hardware_attributes": { "one_node_cluster": true,/'
        file_path = "/etc/nutanix/hardware_config.json"
        enable_one_node_config_cmd = f"source /etc/profile; sudo sed -i '{sed_command}' '{file_path}'"
        
        mock_execute_command.assert_called_with(
            mock_get_ssh_connection.return_value, enable_one_node_config_cmd)
        mock_get_interactive_shell.assert_called_once_with(mock_get_ssh_connection.return_value)
        mock_stop_foundation.assert_called_once_with(mock_get_interactive_shell.return_value)
        mock_restart_genesis.assert_called_once_with(mock_get_interactive_shell.return_value)
        mock_close_ssh_connection.assert_called_with(mock_get_ssh_connection.return_value)
        assert status == True and error_msg == None


    def test_delete_software(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        mock_execute_command.return_value = ("successfully deleted", None)
        result = ssh_cvm.delete_software(version="1.0", software_type="NOS")
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ncli software delete software-type=NOS name=1.0")
        assert result == True
        
        mock_execute_command.return_value = ("failed to delete", "error")
        result = ssh_cvm.delete_software(version="1.0", software_type="NOS")
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ncli software delete software-type=NOS name=1.0")
        assert result == False
        
    def test_check_software_exists(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        mock_execute_command.return_value = ("completed", None)
        
        result = ssh_cvm.check_software_exists(version="1.0", software_type="NOS")
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ncli software ls software-type=NOS name=1.0")
        assert result == True
        
        mock_execute_command.return_value = ("failed", "error")
        result = ssh_cvm.check_software_exists(version="1.0", software_type="NOS")
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ncli software ls software-type=NOS name=1.0")
        assert result == False
        
    def test_upload_software(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        mock_execute_command.return_value = ("completed", None)
        
        status,error_message = ssh_cvm.upload_software(
            metadata_file_path="/path/to/metadata", file_path="/path/to/file", software_type="NOS")

        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            ssh_obj = mock_get_ssh_connection.return_value,
            command = "source /etc/profile; ncli software upload software-type=NOS meta-file-path=/path/to/metadata file-path=/path/to/file",
            timeout=2000)
        assert status == True and error_message == None
        mock_execute_command.return_value = ("failed", "error")
        status,error_message = ssh_cvm.upload_software(
            metadata_file_path="/path/to/metadata", file_path="/path/to/file", software_type="NOS")
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(
            ssh_obj = mock_get_ssh_connection.return_value,
            command = "source /etc/profile; ncli software upload software-type=NOS meta-file-path=/path/to/metadata file-path=/path/to/file",
            timeout=2000)
        assert status == False and error_message == "failederror"
        mock_execute_command.side_effect = Exception("error")
        status,error_message = ssh_cvm.upload_software(
            metadata_file_path="/path/to/metadata", file_path="/path/to/file", software_type="NOS")
        
        assert status == False and str(error_message) == "error" and isinstance(error_message, Exception)
        
    def test_download_files(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        
        mock_execute_command.return_value = ("completed", None)
        cmd = ";".join(["wget -c --timestamp --no-check-certificate {}".format(url) for url in ["http://example.com/file1", "http://example.com/file2"]])
        cmd = "source /etc/profile;{}".format(cmd)
        status,error_msg = ssh_cvm.download_files(url_list=["http://example.com/file1", "http://example.com/file2"])
        
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(ssh_obj = mock_get_ssh_connection.return_value, command = cmd, timeout=300)
        assert status == True and error_msg == None
        
        mock_execute_command.return_value = ("failed", "error")
        status,error_msg = ssh_cvm.download_files(url_list=["http://example.com/file1", "http://example.com/file2"])
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(ssh_obj = mock_get_ssh_connection.return_value, command = cmd, timeout=300)
        assert status == False and error_msg == "failederror"
        
    def test_upload_pc_deploy_software(self, mocker, ssh_cvm):
        mock_file_exists = mocker.patch.object(ssh_cvm, "file_exists")
        mock_download_files = mocker.patch.object(ssh_cvm, "download_files")
        mock_md5sum = mocker.patch.object(ssh_cvm, "get_md5sum_from_file_in_cvm")
        mock_check_software_exists = mocker.patch.object(ssh_cvm, "check_software_exists")
        mock_upload_software = mocker.patch.object(ssh_cvm, "upload_software")
        mock_delete_software = mocker.patch.object(ssh_cvm, "delete_software")
        
        file_url = "test_url.com/abc/file"
        metadata_file_url = "test_url.com/abc/metadata"
        metadata_file_path = "/home/nutanix/{}".format(metadata_file_url.split("/")[-1])
        file_path = "/home/nutanix/{}".format(file_url.split("/")[-1])
        
        #Case 1
        mock_file_exists.return_value = True
        mock_md5sum.return_value = "md5sum abc def"
        mock_check_software_exists.return_value = False
        mock_upload_software.return_value = True, None
        result,error_msg = ssh_cvm.upload_pc_deploy_software(
            pc_version="1.0", metadata_file_url=metadata_file_url, file_url=file_url, md5sum="md5sum")
        #mock_file_exists.assert_called_with(file_path)
 
        mock_md5sum.assert_called_once_with(file_path)
        mock_download_files.assert_not_called()
        mock_check_software_exists.assert_called_once_with(version="1.0", software_type="PRISM_CENTRAL_DEPLOY")
        mock_upload_software.assert_called_once_with(
            metadata_file_path, file_path, software_type="PRISM_CENTRAL_DEPLOY", timeout=2000)
        assert result == True and error_msg == None
        
        #Case 2
        mock_md5sum.return_value = "xyz abc def"
        result,error_msg = ssh_cvm.upload_pc_deploy_software(
            pc_version="1.0", metadata_file_url=metadata_file_url, file_url=file_url, md5sum="md5sum")
        mock_md5sum.assert_called_with(file_path)
        mock_download_files.assert_called_with(url_list=[metadata_file_url, file_url])
    
        assert result == False and error_msg == f"md5sum of file does not match with the file '{file_path}' downloaded in CVM"
        
        #Case 3
        mock_check_software_exists.return_value = True
        result,error_msg = ssh_cvm.upload_pc_deploy_software(
            pc_version="1.0", metadata_file_url=metadata_file_url, file_url=file_url)
        assert result == True and error_msg == None
        
        #Case 4
        mock_delete_software.return_value = False
        result,error_msg = ssh_cvm.upload_pc_deploy_software(
            pc_version="1.0", metadata_file_url=metadata_file_url, file_url=file_url, delete_existing_software=True)
        mock_delete_software.assert_called_once_with(version="1.0", software_type="PRISM_CENTRAL_DEPLOY")
        assert result == False and error_msg == f"test_ip: Failed to delete existing software 1.0"
        
        #Case 5
        mock_file_exists.return_value = False
        result,error_msg = ssh_cvm.upload_pc_deploy_software(
            pc_version="1.0", metadata_file_url=metadata_file_url, file_url=file_url)
        assert result == False and error_msg == f"test_ip: Failed to download files to CVM"
        
        


    def test_file_exists(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        
        mock_execute_command.return_value = ("completed", None)
        
        result = ssh_cvm.file_exists(file_path="/path/to/file")

        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ls /path/to/file")
        assert result == True
        
        mock_execute_command.return_value = ("failed", "error")
        result = ssh_cvm.file_exists(file_path="/path/to/file")        
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; ls /path/to/file")
        assert result == False
        
    def test_get_md5sum_from_file_in_cvm(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_execute_command = mocker.patch.object(ssh_cvm, "execute_command")
        
        mock_execute_command.return_value = ("md5sum", None)
        result = ssh_cvm.get_md5sum_from_file_in_cvm(file_path="/path/to/file")
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_once_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; md5sum /path/to/file", timeout = 200)
        assert result == "md5sum"
        
        mock_execute_command.return_value = ("failed", "error")
        result = ssh_cvm.get_md5sum_from_file_in_cvm(file_path="/path/to/file")
        mock_get_ssh_connection.assert_called_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_execute_command.assert_called_with(
            ssh_obj = mock_get_ssh_connection.return_value, command = "source /etc/profile; md5sum /path/to/file", timeout = 200)
        assert result == "None"
        
    def test_enable_replication_ports(self, mocker, ssh_cvm):
        mock_get_ssh_connection = mocker.patch.object(ssh_cvm, "get_ssh_connection")
        mock_get_interactive_shell = mocker.patch.object(ssh_cvm, "get_interactive_shell")
        mock_send_to_interactive_channel = mocker.patch.object(ssh_cvm, "send_to_interactive_channel")
        mock_receive_from_interactive_channel = mocker.patch.object(ssh_cvm, "receive_from_interactive_channel")
        
        mock_receive_from_interactive_channel.side_effect = ["Firewall config updated\n"] * 3
        mock_sleep = mocker.patch('time.sleep')
        receive,error_msg = ssh_cvm.enable_replication_ports(ports=["8080", "4000"])
        
        cmd = f"allssh modify_firewall -f -o open -i eth0 -p 8080,4000 -a"
        
        mock_get_ssh_connection.assert_called_once_with(self.cvm_ip, self.cvm_username, self.cvm_password)
        mock_send_to_interactive_channel.assert_called_once_with(mock_get_interactive_shell.return_value, cmd)
        mock_receive_from_interactive_channel.assert_called_with(mock_get_interactive_shell.return_value)
        assert receive == ("Firewall config updated\n"*3) and error_msg == None
 
                
        