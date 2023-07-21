import select
import paramiko
import time
from helpers.log_utils import get_logger

logger = get_logger(__name__)

class SSH:
    def __init__(self, cvm_ip, cvm_username, cvm_password, fc_logger = None):
        """
        Args:
            cvm_ip (str): CVM IP
            cvm_username (str): CVM username
            cvm_password (str): CVM password
        """
        self.cvm_ip = cvm_ip
        self.cvm_username = cvm_username
        self.cvm_password = cvm_password
        self.logger = fc_logger or logger
    
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
        self.logger.info(command)
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
            self.logger.error("Error while getting interactive channel: {0} for CMV {1}".format(e, self.cvm_ip))
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
                self.logger.error("Error: Time out waiting for command '{0}' in CVM {1}".format(command, self.cvm_ip))
                return response
        except Exception as e:
            self.logger.error("Error while executing command '{0}' in CMV {1}. Error: {2}".format(command, self.cvm_ip, e))

    def send_to_interactive_channel(self, interactive_channel: paramiko.SSHClient.invoke_shell, command, timeout=60):
        wait_time = timeout
        poll_frequency = 0.1
        try:
            interactive_channel.settimeout(timeout)
            while not interactive_channel.send_ready():
                if wait_time <= 0:
                    self.logger.error("Error: Time out waiting for command '{0}' in CVM {1}".format(command, self.cvm_ip))
                time.sleep(poll_frequency)
                wait_time -= poll_frequency

            # At this point, the channel should be ready
            interactive_channel.send("{command}{sep}".format(command=command,
                                                            sep="\n"))
        except Exception as e:
            self.logger.error("Command '{0}' execution failed in CMV {1}. Error: {2}".format(command, self.cvm_ip, e))

    def receive_from_interactive_channel(self, interactive_channel: paramiko.SSHClient.invoke_shell):
        response = ""
        bufsize = 4096
        response += interactive_channel.recv(bufsize).decode('utf-8')
        try:
            while interactive_channel.recv_ready():
                response += interactive_channel.recv(bufsize).decode('utf-8')
        except Exception as e:
            self.logger.error("Exception receiving response in CVM {0}.Error: {1}".format(self.cvm_ip, e))
        return response

    def stop_foundation(self, int_chan: paramiko.SSHClient):
        """Stop Foundation in CVM

        Args:
            int_chan (paramiko.SSHClient): paramiko SSHClient object

        Returns:
            bool: True if Foundation is stopped in CVM else False
        """
        stop_foundation = "source /etc/profile; genesis stop foundation"
        self.send_to_interactive_channel(int_chan, stop_foundation)
        time_to_wait = 120
        self.logger.info(f"{self.cvm_ip} - Genesis Stop Foundation...")
        stop_foundation = False
        start_time = time.time()
        while not stop_foundation:
            if time.time() - start_time > time_to_wait:
                self.logger.error("Waited for %s mins, task not finished"
                    % (time_to_wait / 60, self.receive_from_interactive_channel(int_chan)))
            receive = self.receive_from_interactive_channel(int_chan)
            self.logger.debug(receive)
            if receive is not None and receive != "":
                stop_foundation = True
                self.logger.info(f"{self.cvm_ip} - Foundation stopped")
        return stop_foundation

    def restart_genesis(self, int_chan: paramiko.SSHClient):
        """Restart genesis in CVM

        Args:
            int_chan (paramiko.SSHClient): paramiko SSHClient object

        Returns:
            bool: True if Genesis is re-started in CVM else False
        """
        restart_genesis = "source /etc/profile; genesis restart"
        message = "Genesis started on pids"
        self.logger.info("Restarting genesis...")
        self.send_to_interactive_channel(int_chan, restart_genesis)
        start_time = time.time()
        time_to_wait = 180
        while True:
            if time.time() - start_time > time_to_wait:
                self.logger.error("Waited for %s mins, task not finished"
                    % (time_to_wait / 60, self.receive_from_interactive_channel(int_chan)))
            receive = self.receive_from_interactive_channel(int_chan)
            self.logger.debug(receive)
            if receive is not None and receive != "" and message in receive:
                self.logger.info(f"{self.cvm_ip} - Restarted genesis")
                return True

    def update_heartbeat_interval_mins(self, interval_min: int = 1):
        """Update the heartbeat interval in CVM FC settings

        Args:
            interval_min (int, optional): Interval time between each check. Defaults to 1.

        Returns:
            tuple: status, error_message
        """
        status, error_message = False, None
        try:
            ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
            update_file_command = "sed -r -i '/heartbeat_interval_mins/ s/(^.*)(:.*)/\\1: {0},/g' ~/foundation/config/foundation_settings.json".format(interval_min)
            self.logger.debug(f"Executing Command: {update_file_command}")
            _, err = self.execute_command(ssh_obj, update_file_command)
            if err:
                error_message = f"{self.cvm_ip} - Error Updating heartbeat interval mins: {err}"
                if "No such file or directory" in err:
                    retry = 0
                    while "No such file or directory" in err:
                        self.logger.warning(f"{self.cvm_ip}: Wait for the file foundation_settings.json to be created in CVM")
                        time.sleep(5)
                        _, err = self.execute_command(ssh_obj, update_file_command)
                        retry += 1
                        if err:
                            error_message = f"{self.cvm_ip} - Error Updating heartbeat interval mins: {err}"
                        else:
                            self.logger.info(f"{self.cvm_ip} - Updated heartbeat interval mins")
                            error_message = None
                            break
                        if retry > 20:
                            return status, error_message
                else:
                    return status, error_message
            try:
                self.logger.info("Updated heartbeat interval mins")
                time.sleep(2)
                int_chan = self.get_interactive_shell(ssh_obj)
                stop_foundation = self.stop_foundation(int_chan)
                if stop_foundation:
                    if self.restart_genesis(int_chan):
                        status = True
                    else:
                        error_message = f"{self.cvm_ip}: Failed to restart genesis"
                else:
                    error_message = f"{self.cvm_ip}: Failed to stop foundation"
            except Exception as e:
                self.logger.error(f"{self.cvm_ip} - Error: {e}")
                error_message =  e
            finally:
                int_chan.close()
        except Exception as e:
            self.logger.error(f"{self.cvm_ip}: Error {e}")
            error_message = e
        finally:
            self.close_ssh_connection(ssh_obj)
        return status, error_message

    def enable_one_node(self):
        """Enable one node support in CVM

        Returns:
            tuple: status, error_message
        """
        status, error_message = False, None
        try:
            ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
            # Check if one node is already enabled
            cat_command = "source /etc/profile; cat /etc/nutanix/hardware_config.json | grep one_node"
            out, err = self.execute_command(ssh_obj, cat_command)
            if not out and not err:
                time.sleep(2)
                sed_command = 's/"hardware_attributes": {/"hardware_attributes": { "one_node_cluster": true,/'
                file_path = "/etc/nutanix/hardware_config.json"
                enable_one_node_config_cmd = f"source /etc/profile; sudo sed -i '{sed_command}' '{file_path}'"
                self.logger.warning(f"Executing Command: {enable_one_node_config_cmd}")
                out, err = self.execute_command(ssh_obj, enable_one_node_config_cmd)
                if out or err:
                    error_message = f"{self.cvm_ip} - Error Updating hardware config file: {out} {err}"
                else:
                    time.sleep(2)
                    try:
                        int_chan = self.get_interactive_shell(ssh_obj)
                        stop_foundation = self.stop_foundation(int_chan)
                        if stop_foundation:
                            if self.restart_genesis(int_chan):
                                status = True
                            else:
                                error_message = f"{self.cvm_ip}: Failed to restart genesis"
                        else:
                            error_message = f"{self.cvm_ip}: Failed to stop foundation"
                    except Exception as e:
                        self.logger.error(f"{self.cvm_ip} - Error: {e}")
                        error_message =  e
                    finally:
                        int_chan.close()
            elif out:
                self.logger.info(f"{self.cvm_ip}: One node support is already enabled in nodes")
            else:
                self.logger.error(err)
                error_message = err
        except Exception as e:
            self.logger.error(f"{self.cvm_ip}: Error {e}")
            error_message = e
        finally:
            self.close_ssh_connection(ssh_obj)
        return status, error_message
