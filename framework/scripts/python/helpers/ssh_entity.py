import select
import paramiko
import time
import logging
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class SSHEntity:
    def __init__(self, ip, username, password):
        """
        Args:
            ip (str): IP Address
            username (str): Username
            password (str): Password
        """
        self.ip = ip
        self.username = username
        self.password = password
        self.logger = logger
        # Setting the logging level for paramiko to warning
        # so it does not log the all INFO related to authentication in OUTPUT
        logging.getLogger("paramiko").setLevel(logging.WARNING)

    def get_ssh_connection(self, ip, username, password):
        try:
            # Open new SSH client
            
            ssh_obj = paramiko.SSHClient()
            # Disable host key check
            ssh_obj.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_obj.connect(ip, username=username, password=password)
            return ssh_obj
        except Exception as e:
            self.logger.error(e)

    def close_ssh_connection(self, ssh_obj: paramiko.SSHClient):
        """Close SSH connection

        Args:
            ssh_obj (paramiko.SSHClient): ssh client object
        """
        try:
            ssh_obj.close()
        except Exception as e:
            self.logger.error(f"Error while closing SSH connection: {e}")

    def execute_command(self, ssh_obj: paramiko.SSHClient, command, timeout = 60):
        """
        Execute command in non-interactive mode
        """
        self.logger.debug(command)
        stdin, stdout, stderr = ssh_obj.exec_command(command, timeout)
        # get the shared channel for stdout/stderr/stdin
        channel = stdout.channel

        # we do not need stdin.
        stdin.close()
        # indicate that we're not going to write to that channel anymore
        channel.shutdown_write()

        # set buffer size
        bufsize = 4096
        # read stdout/stderr in order to prevent read block hangs
        stdout_chunks, stderr_chunks = "", ""
        stdout_chunks += stdout.channel.recv(bufsize).decode('utf-8')
        stderr_chunks += stderr.channel.recv(bufsize).decode('utf-8')
        # stop if channel was closed prematurely, and there is no data in the buffers.
        while not channel.closed or channel.recv_ready() or channel.recv_stderr_ready():
            got_chunk = False
            readq, _, _ = select.select([stdout.channel], [], [], timeout)
            for c in readq:
                if c.recv_ready(): 
                    stdout_chunks += stdout.channel.recv(bufsize).decode('utf-8')
                    got_chunk = True
                if c.recv_stderr_ready(): 
                    stderr_chunks += stderr.channel.recv_stderr(bufsize).decode('utf-8')  
                    got_chunk = True

            if not got_chunk \
                and stdout.channel.exit_status_ready() \
                and not stderr.channel.recv_stderr_ready() \
                and not stdout.channel.recv_ready(): 
                stdout.channel.shutdown_read()  
                # close the channel
                stdout.channel.close()
                break

        # close all the pseudofiles
        stdout.close()
        stderr.close()
        return stdout_chunks, stderr_chunks

    def get_interactive_shell(self, ssh_obj: paramiko.SSHClient):
        """Get the interactive shell

        Args:
            ssh_obj (paramiko.SSHClient): paramiko SSHClient object

        Returns:
            obj: Interactive shell
        """
        try:
            return ssh_obj.invoke_shell()
        except Exception as e:
            self.logger.error("Error while getting interactive channel: {0} for {1}".format(e, self.ip))
            return None

    def execute_on_interactive_channel(self, interactive_channel, command, pattern):
        """Execute commands in interactive channel

        Args:
            interactive_channel (obj): paramiko SSHClient shell object
            command (str): Command to execute
            pattern (str): Pattern match to exit the 

        Returns:
            _type_: _description_
        """
        try:
            response = ""
            timeout = 60
            self.send_to_interactive_channel(command=command,
                                            interactive_channel=interactive_channel,
                                            timeout=timeout)
            wait_time = timeout
            poll_frequency = 0.1
            while wait_time > 0:
                response += self.receive_from_interactive_channel(
                interactive_channel=interactive_channel)
                if pattern in response:
                    self.logger.debug("response>> '{response}'".format(response=response))
                    return response
                time.sleep(poll_frequency)
                wait_time -= poll_frequency
            else:
                self.logger.error("Error: Time out waiting for command '{0}' in CVM {1}".format(command, self.ip))
                return response
        except Exception as e:
            self.logger.error("Error while executing command '{0}' in {1}. Error: {2}".format(command, self.ip, e))

    def send_to_interactive_channel(self, interactive_channel: paramiko.SSHClient.invoke_shell, command, timeout=60):
        wait_time = timeout
        poll_frequency = 0.1
        try:
            interactive_channel.settimeout(timeout)
            while not interactive_channel.send_ready():
                if wait_time <= 0:
                    self.logger.error("Error: Time out waiting for command '{0}' in CVM {1}".format(command, self.ip))
                time.sleep(poll_frequency)
                wait_time -= poll_frequency

            # At this point, the channel should be ready
            interactive_channel.send("{command}{sep}".format(command=command,
                                                            sep="\n"))
        except Exception as e:
            self.logger.error("Command '{0}' execution failed in {1}. Error: {2}".format(command, self.ip, e))

    def receive_from_interactive_channel(self, interactive_channel: paramiko.SSHClient.invoke_shell):
        response = ""
        bufsize = 4096
        response += interactive_channel.recv(bufsize).decode('utf-8')
        try:
            while interactive_channel.recv_ready():
                response += interactive_channel.recv(bufsize).decode('utf-8')
        except Exception as e:
            self.logger.error("Exception receiving response in CVM {0}.Error: {1}".format(self.ip, e))
        return response
