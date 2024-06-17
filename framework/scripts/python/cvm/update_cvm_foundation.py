from framework.scripts.python.cvm.cvm_script import CvmScript
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.ssh_cvm import SSHCVM
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class UpdateCvmFoundation(CvmScript):
    """
    Update CVM foundation
    """
    def __init__(self, data: dict, **kwargs):
        super(UpdateCvmFoundation, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cvm(self, cvm_ip, cvm_details):
        """
        Args:
            cvm_ip (str): CVM IP
            cvm_details:
                cvm_credential (str): CVM credential to fetch from vault in global.yml
                foundation_build_url (str): Foundation URL to download the tar file from
                foundation_version (str): Foundation version to download the tar file from
                nameserver (str, Optional): Optional. Nameserver to add to /etc/resolv.conf
                downgrade (boolean, Optional): Optional. True if Downgrade the foundation version
        """
        try:
            if not cvm_details.get("cvm_credential"):
                self.exceptions.append(f"{cvm_ip}: CVM Credentials are not provided")
                return
            cvm_username, cvm_password = (read_creds(data=self.data, credential=cvm_details["cvm_credential"]))
            ssh_cvm = SSHCVM(cvm_ip, cvm_username, cvm_password)
            # Update namerser if provided
            if cvm_details.get("nameserver"):
                status, error = ssh_cvm.update_resolv_conf(cvm_details["nameserver"])
                # Not going to exit if nameserver update fails, proceed with downloading file.
                if not status:
                    self.logger.warning(f"{cvm_ip}: Failed to update nameserver in resolv.conf {error}")

            # Update the CVM Foundation
            status, error_message = ssh_cvm.update_cvm_foundation(foundation_url_path=cvm_details["foundation_build_url"],
                                                                  downgrade=cvm_details.get("downgrade", False))
            if not status:
                self.exceptions.append(f"{cvm_ip}: Failed to update CVM foundation: {error_message}")
        except Exception as e:
            self.exceptions.append(f"Exception occured while updating CVM Foundation: {e}")

    def verify_single_cvm(self, cvm_ip, cvm_details):
        self.results["cvms"] = {"UpdateCvmFoundation": {}}
        try:
            self.results["cvms"]["UpdateCvmFoundation"][cvm_ip] = "Can't Verify"
            cvm_username, cvm_password = (read_creds(data=self.data, credential=cvm_details["cvm_credential"]))
            ssh_cvm = SSHCVM(cvm_ip, cvm_username, cvm_password)
            status, output = ssh_cvm.get_foundation_version()
            self.logger.debug(output)
            if not status:
                self.logger.error(f"{cvm_ip} - Failed to fetch CVM foundation version: {output}")
                return
            if cvm_details["foundation_version"] in output:
                self.results["cvms"]["UpdateCvmFoundation"][cvm_ip] = "PASS"
            else:
                self.results["cvms"]["UpdateCvmFoundation"][cvm_ip] = "FAIL"
        except Exception as e:
            self.logger.error(e)
