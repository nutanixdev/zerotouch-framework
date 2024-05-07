from typing import Optional, List
import paramiko
import time
import re
from .ssh_entity import SSHEntity
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class SSHCVM(SSHEntity):
    NUTANIX_DEFAULT_USERNAME = "nutanix"
    NUTANIX_DEFAULT_PASSWORD = "nutanix/4u"

    def __init__(self, cvm_ip, cvm_username=None, cvm_password=None):
        """
        Args:
            cvm_ip (str): CVM IP
            cvm_username (str): CVM username
            cvm_password (str): CVM password
        """
        self.cvm_ip = cvm_ip
        self.cvm_username = cvm_username or self.NUTANIX_DEFAULT_USERNAME
        self.cvm_password = cvm_password or self.NUTANIX_DEFAULT_PASSWORD
        super(SSHCVM, self).__init__(cvm_ip, cvm_username, cvm_password)
        self.logger = logger

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
                self.logger.error("Waited for %s mins, task not finished" % (time_to_wait / 60))
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
                self.logger.error("Waited for %s mins, task not finished" % (time_to_wait / 60))
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
            update_file_command = "sed -r -i '/heartbeat_interval_mins/ s/(^.*)(:.*)/\\1: {0},/g' ~/foundation/config/foundation_settings.json".format(
                interval_min)
            self.logger.debug(f"Executing Command: {update_file_command}")
            _, err = self.execute_command(ssh_obj, update_file_command)
            if err:
                error_message = f"{self.cvm_ip} - Error Updating heartbeat interval mins: {err}"
                if "No such file or directory" in err:
                    retry = 0
                    while "No such file or directory" in err:
                        self.logger.warning(
                            f"{self.cvm_ip}: Wait for the file foundation_settings.json to be created in CVM")
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
                error_message = e
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
                self.logger.debug(f"Executing Command: {enable_one_node_config_cmd}")
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
                        error_message = e
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

    def delete_software(self, version: str, software_type: str):
        """
        Delete software uploaded to PE
        Args:
            version (str): Version to delete
            software_type (str): Software type
            eg, NOS, PRISM_CENTRAL, PRISM_CENTRAL_DEPLOY

        Returns:
            tuple: status (bool), error_message (str)
        """
        ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
        cmd = "source /etc/profile; ncli software delete software-type={} name={}".format(software_type, version)
        output, err = self.execute_command(ssh_obj=ssh_obj, command=cmd)
        self.logger.debug(output)
        self.logger.debug(err)
        if "successfully deleted" in output.lower() or "successfully deleted" in err.lower():
            return True
        return False

    def check_software_exists(self, version: str, software_type: str):
        """
        Check if software exists in PE
        Args:
            version (str): Version to delete
            software_type (str): Software type
            eg, NOS, PRISM_CENTRAL, PRISM_CENTRAL_DEPLOY

        Returns:
            bool: True if software exists, else False
        """
        self.logger.info(f"{self.cvm_ip}: Checking if Software already exists")
        ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
        cmd = "source /etc/profile; ncli software ls software-type={} name={}".format(software_type, version)
        output, err = self.execute_command(ssh_obj=ssh_obj, command=cmd)
        self.logger.debug(output)
        self.logger.debug(err)
        if "completed" in output.lower() or "completed" in err.lower():
            return True
        else:
            return False

    def upload_software(self, metadata_file_path, file_path, software_type, timeout=2000):
        """
        Upload Software to PE
        Args:
            metadata_file_path(str): the metadata file path
            file_path(str): the path of the tar ball file
            software_type (str): Software type
            timeout (int): timeout
            eg, NOS, PRISM_CENTRAL, PRISM_CENTRAL_DEPLOY
        Returns:
            tuple: status(bool), error_message(str)
        """
        self.logger.info(f"{self.cvm_ip}: Uploading software type: {software_type}")
        status, error_message = False, None
        try:
            ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
            cmd = "source /etc/profile; ncli software upload software-type={} meta-file-path={} file-path={}". \
                format(software_type, metadata_file_path, file_path)
            output, err = self.execute_command(ssh_obj=ssh_obj, command=cmd, timeout=timeout)
            if "completed" in output.lower() or err.lower():
                self.logger.info(output)
                status = True
            else:
                error_message = output.lower() + err.lower()
            return status, error_message
        except Exception as e:
            return status, e

    def download_files(self, url_list: List, timeout=300):
        """
        The function to download a list of files
        Args:
            url_list(list): The list of the urls to download
            timeout(int): Command timeout

        Returns:
            dict: The command output
        """
        self.logger.info(f"Downloading files from URL(s): {url_list}")
        status = False
        try:
            ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
            cmd = ";".join(["wget -c --timestamp --no-check-certificate {}".format(url) for url in url_list])
            cmd = "source /etc/profile;{}".format(cmd)
            out, err = self.execute_command(ssh_obj=ssh_obj, command=cmd, timeout=timeout)
            self.logger.info(out)
            if err:
                return status, out + err
            return True, None
        except Exception as e:
            return status, e

    def upload_pc_deploy_software(self, pc_version: str, metadata_file_url: str, file_url: str,
                                  md5sum: str = None, delete_existing_software: bool = False):
        """Upload PC Software to PE

        Args:
            pc_version (str): PC Version name
            metadata_file_url (str): Metadata file URL path to download
            file_url (str): PC tar file URL path to upload
            md5sum (_type_, optional): md5sum to check if file already exists. Defaults to None.
            delete_existing_software (bool, optional): Delete if same pc version is already uploaded.
                                                  Defaults to False.

        Returns:
            tuple: status(bool), error_message(str)
        """
        metadata_file_path = "/home/nutanix/{}".format(metadata_file_url.split("/")[-1])
        file_path = "/home/nutanix/{}".format(file_url.split("/")[-1])
        software_type = "PRISM_CENTRAL_DEPLOY"
        download_file = False
        # If file already exists check the MD5SUM, if it doesn't match download files to CVM
        if self.file_exists(file_path) and self.file_exists(metadata_file_path):
            if md5sum:
                self.logger.info(f"Checking MD5SUM of file: {file_path}")
                cvm_file_md5sum = self.get_md5sum_from_file_in_cvm(file_path)
                if md5sum == cvm_file_md5sum.split()[0]:
                    self.logger.warning(
                        f"md5sum of file match with the file in CVM {file_path}. Skipping file download.")
                else:
                    self.logger.warning(
                        f"md5sum of file does not match with the file in CVM {file_path}. Proceeding to download.")
                    download_file = True
            else:
                download_file = True
        else:
            download_file = True

        # Download the files
        if download_file:
            self.logger.info(f"{self.cvm_ip}: Downloading metadata & tar files...")
            self.download_files(url_list=[metadata_file_url, file_url])
            self.logger.info(f"{self.cvm_ip}: Checking if the files are downloaded in CVM")
            if not self.file_exists(file_path) and not self.file_exists(metadata_file_url):
                return False, f"{self.cvm_ip}: Failed to download files to CVM"
            else:
                self.logger.debug(f"{self.cvm_ip}: Successfully downloaded the tar & metadata files to the CVM")
                # Compare md5sum if md5sum is provided - additional check
                if md5sum:
                    cvm_file_md5sum = self.get_md5sum_from_file_in_cvm(file_path)
                    if md5sum == cvm_file_md5sum.split()[0]:
                        self.logger.info(f"md5sum of file match with the file '{file_path}' downloaed in CVM")
                    else:
                        return False, f"md5sum of file does not match with the file '{file_path}' downloaded in CVM"

        if self.check_software_exists(version=pc_version, software_type=software_type):
            self.logger.info(f"{self.cvm_ip}: Software Already exists")
            if delete_existing_software:
                # Delete any old software from PE
                self.logger.info(f"{self.cvm_ip}: Delete already existing software {pc_version}")
                status = self.delete_software(version=pc_version, software_type=software_type)
                if status:
                    self.logger.info(f"{self.cvm_ip}: Successfully deleted software {pc_version}")
                else:
                    self.logger.error(f"{self.cvm_ip}: Failed to deleted exisiting software {pc_version}")
                    return False, f"{self.cvm_ip}: Failed to deleted exisiting software {pc_version}"
                # Upload software to PE
                return self.upload_software(metadata_file_path, file_path, software_type=software_type, timeout=2000)
            return True, None
        else:
            self.logger.info(f"{self.cvm_ip}: Uploading software to PE...")
            return self.upload_software(metadata_file_path, file_path, software_type=software_type, timeout=2000)

    def file_exists(self, file_path):
        """
        Check if a file exists in the specified path
        Args:
            file_path (str): file path
        Returns:
            bool: True if file exist, else False
        """
        self.logger.info(f"Check if the file {file_path!r} exists")
        ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
        cmd = "source /etc/profile; ls %s" % file_path
        try:
            out, err = self.execute_command(ssh_obj=ssh_obj, command=cmd)
            if err or 'cannot access' in out:
                return False
            return True
        except Exception as e:
            self.logger.error(e)
            return False

    def get_md5sum_from_file_in_cvm(self, file_path):
        """
        returns md5sum from pcvm file
        Args:
            file_path(str): file path to check md5sum
        Returns: md5sum
        """
        cmd = f"source /etc/profile; md5sum {file_path}"
        md5sum_response = "None"
        try:
            ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
            out, err = self.execute_command(ssh_obj=ssh_obj, command=cmd, timeout=200)
            if not err:
                self.logger.info(f"Md5sum of file {file_path} is {out}")
                return out
        except Exception as e:
            self.logger.error(e)
        return md5sum_response

    def enable_replication_ports(self, ports: Optional[list] = None) -> (str, str):
        """
        Enable replication ports in cvms
        """
        ports = ",".join(ports) if ports else "2020,2030,2036,2073,2090"
        ssh_obj = self.get_ssh_connection(self.cvm_ip, self.cvm_username, self.cvm_password)
        int_chan = self.get_interactive_shell(ssh_obj)

        cmd = f"allssh modify_firewall -f -o open -i eth0 -p {ports} -a"

        time_to_wait = 120
        self.send_to_interactive_channel(int_chan, cmd)
        start_time = time.time()
        receive = ""

        while (time.time() - start_time) <= time_to_wait:
            receive += self.receive_from_interactive_channel(int_chan)
            # todo here we are assuming we are opening only for 3 node clusters. Need to modify the logic accordingly
            if len([m.start() for m in re.finditer("Firewall config updated", receive)]) == 3:
                return receive, None
            time.sleep(10)

        return receive, "Operation, timed out or failed!"
