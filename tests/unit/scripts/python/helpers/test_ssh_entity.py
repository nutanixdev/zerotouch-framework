import pytest
import paramiko
from unittest.mock import MagicMock, Mock
from framework.scripts.python.helpers.ssh_entity import SSHEntity
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)

class TestSSHEntity:
    @pytest.fixture
    def ssh_entity(self):
        self.ip = "test_ip"
        self.username = "test_username"
        self.password = "test_password"
        self.logger = MagicMock()
        return SSHEntity(
            ip=self.ip, username=self.username,
            password=self.password
        )

    def test_ssh_entity_init(self, ssh_entity):
        assert ssh_entity.ip == self.ip
        assert ssh_entity.username == self.username
        assert ssh_entity.password == self.password
        assert isinstance(ssh_entity, SSHEntity)

    def test_get_ssh_connection(self, mocker, ssh_entity):
        mock_ssh_client = mocker.patch.object(paramiko, "SSHClient")
        mock_ssh = MagicMock()
        mock_ssh_client.return_value = mock_ssh
        mock_logger = mocker.patch.object(ssh_entity, "logger")

        connection = ssh_entity.get_ssh_connection(
            ssh_entity.ip, ssh_entity.username, ssh_entity.password
            )

        mock_ssh_client.assert_called_once()
        mock_ssh.set_missing_host_key_policy.assert_called_once()
        mock_ssh.connect.assert_called_once_with(
            ssh_entity.ip, username=ssh_entity.username, password=ssh_entity.password)
        assert connection == mock_ssh
        
        # Test AuthenticationException
        mock_ssh_client.side_effect = [paramiko.ssh_exception.AuthenticationException("Authentication failed")]
        ssh_entity.get_ssh_connection(
            ssh_entity.ip, ssh_entity.username, ssh_entity.password
        )
        assert isinstance(mock_logger.error.call_args[0][0], paramiko.ssh_exception.AuthenticationException)
        assert str(mock_logger.error.call_args[0][0]) == "Authentication failed"
        mock_logger.error.assert_called_once()


    def test_close_ssh_connection(self, mocker, ssh_entity):
        mock_ssh = MagicMock()
        ssh_entity.close_ssh_connection(mock_ssh)
        mock_logger = mocker.patch.object(ssh_entity, "logger")

        mock_ssh.close.assert_called_once()
        
        mock_ssh.close.side_effect = [Exception("Unexpected error")]
        ssh_entity.close_ssh_connection(mock_ssh)
        assert str(mock_logger.error.call_args[0][0]) == "Error while closing SSH connection: Unexpected error"
        mock_logger.error.assert_called_once()

    def test_execute_command(self, mocker, ssh_entity):
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_channel = MagicMock()
        
        # Set up channel closed attribute to eventually stop the loop
        def close_channel():
            mock_channel.closed = True
            return False
        
        # To simulate select.select behavior
        def mock_select(rlist, wlist, xlist, timeout):
            if mock_channel in rlist:
                return ([mock_channel], [], [])
            return ([], [], [])
        
        mock_ssh.exec_command.return_value = (Mock(), mock_stdout, mock_stderr)
        mock_stdout.channel = mock_channel
        mock_stderr.channel = mock_channel
        mock_channel.recv_ready.side_effect = [True, False, close_channel()]
        mock_channel.recv.side_effect = [b'output', b'']
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b'error'
        mock_channel.fileno.return_value = 1

        mocker.patch('select.select', side_effect=mock_select)

        stdout, stderr = ssh_entity.execute_command(mock_ssh, "ls")

        assert stdout == "output"
        assert stderr == "error"

    def test_get_interactive_shell(self, mocker, ssh_entity):
        mock_ssh = MagicMock()
        mock_shell = MagicMock()
        mock_ssh.invoke_shell.return_value = mock_shell
        mock_logger = mocker.patch.object(ssh_entity, "logger")

        shell = ssh_entity.get_interactive_shell(mock_ssh)

        mock_ssh.invoke_shell.assert_called_once()
        assert shell == mock_shell
        mock_ssh.invoke_shell.side_effect = [Exception("Error while getting interactive channel")]
        shell = ssh_entity.get_interactive_shell(mock_ssh)
        assert str(mock_logger.error.call_args[0][0]) == "Error while getting interactive channel: Error while getting interactive channel for test_ip"
        mock_logger.error.assert_called_once()
        assert shell is None

    def test_execute_on_interactive_channel(self, ssh_entity):
        mock_channel = MagicMock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b'pattern'

        response = ssh_entity.execute_on_interactive_channel(mock_channel, "command", "pattern")

        assert "pattern" in response

    def test_send_to_interactive_channel(self, ssh_entity):
        mock_channel = MagicMock()

        ssh_entity.send_to_interactive_channel(mock_channel, "command")

        mock_channel.send.assert_called_with("command\n")

    def test_receive_from_interactive_channel(self, mocker, ssh_entity):
        mock_channel = MagicMock()
        
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b'response_'
        mock_logger = mocker.patch.object(ssh_entity, "logger")

        response = ssh_entity.receive_from_interactive_channel(mock_channel)

        assert response == "response_response_" # response_ is appended twice
        mock_channel.recv.assert_called_with(4096)
        
        mock_channel.recv_ready.side_effect = [Exception("Error while receiving data")]
        response = ssh_entity.receive_from_interactive_channel(mock_channel)
        assert str(mock_logger.error.call_args[0][0]) == "Exception receiving response in CVM test_ip.Error: Error while receiving data"
        mock_logger.error.assert_called_once()
        assert response == "response_"
    
    
    