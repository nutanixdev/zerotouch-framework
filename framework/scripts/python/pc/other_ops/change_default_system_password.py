import time
from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.utils_manager import UtilsManager
from framework.scripts.python.helpers.v2.cluster import Cluster as PcCluster
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import read_creds
from framework.scripts.python.script import Script

logger = get_logger(__name__)


class ChangeDefaultAdminPasswordPc(Script):
    """
    Change default PC admin password
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.default_pc_password = self.data.get('default_pc_password') or self.DEFAULT_SYSTEM_PASSWORD
        self.default_pc_session = RestAPIUtil(self.data['pc_ip'], user=self.DEFAULT_USERNAME,
                                              pwd=self.default_pc_password,
                                              port="9440", secured=True)
        super(ChangeDefaultAdminPasswordPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def change_default_password(self, old_password: str, new_pc_password: str):
        default_system_password = UtilsManager(self.default_pc_session)
        response = default_system_password.change_default_system_password(old_password, new_pc_password)

        if response.get("value"):
            self.logger.info(f"Default System password updated with new password the PC {self.data['pc_ip']!r}")
        else:
            raise Exception(f"Could not change the PC password {self.data['pc_ip']!r}. Error: {response}")
        # Waiting for password sync
        time.sleep(30)

    def execute(self):
        admin_credential = self.data.get("new_pc_admin_credential")

        if not admin_credential:
            raise Exception("No admin credential found!")
        # get credentials from the payload
        try:
            _, new_pc_password = read_creds(data=self.data, credential=admin_credential)
        except Exception as e:
            self.exceptions.append(e)
            return

        if new_pc_password == self.DEFAULT_SYSTEM_PASSWORD:
            self.logger.error("New Password specified is same as default password for the PC ...")
            return

        try:
            self.change_default_password(self.default_pc_password, new_pc_password)
        except Exception as e:
            self.exceptions.append(
                f"Change_default_password failed for the PC {self.data['pc_ip']!r} with the error: {e}")

    def verify(self):
        try:
            self.results = {
                "Change_Default_Admin_password": "CAN'T VERIFY"
            }

            # Check if password is changed
            try:
                endpoint = "cluster"
                cluster_obj = PcCluster(self.default_pc_session)
                cluster_obj.read(endpoint=endpoint)
            except Exception:
                # if it fails, i.e default password doesn't work, password is changed
                self.results["Change_Default_Admin_password"] = "PASS"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for the PC "
                             f"{self.data['pc_ip']!r}")
