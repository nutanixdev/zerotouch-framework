import time
from typing import Dict
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.utils_manager import UtilsManager
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class ChangeDefaultAdminPasswordPe(ClusterScript):
    """
    Change default PE password
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        super(ChangeDefaultAdminPasswordPe, self).__init__(data, **kwargs)
        self.default_pe_password = self.data.get('default_pe_password') or self.DEFAULT_SYSTEM_PASSWORD
        self.logger = self.logger or logger

    def change_default_password(self, pe_session: RestAPIUtil, old_password: str, new_pe_password: str, cluster_info):
        default_system_password = UtilsManager(pe_session)
        response = default_system_password.change_default_system_password(old_password, new_pe_password)

        if response.get("value"):
            self.logger.info(f"Default System password updated with new password in {cluster_info!r}")
        else:
            raise Exception(f"Could not change the PE password in {cluster_info!r}. Error: {response}")
        # Waiting for password sync
        time.sleep(30)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        new_pe_admin_credential = cluster_details.get('new_pe_admin_credential')

        if not new_pe_admin_credential:
            raise Exception("No admin credential found!")

        # get credentials from the payload
        try:
            _, new_pe_password = read_creds(data=self.data, credential=new_pe_admin_credential)
        except Exception as e:
            self.exceptions.append(e)
            return

        if new_pe_password == self.DEFAULT_SYSTEM_PASSWORD:
            self.logger.error(f"New Password specified is same as default password for the cluster...")
            return

        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"
        default_pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                         pwd=self.default_pe_password,
                                         port="9440", secured=True)
        try:
            self.change_default_password(default_pe_session, self.default_pe_password,
                                         new_pe_password, cluster_info)
        except Exception as e:
            self.exceptions.append(f"Change_default_password failed for the cluster {cluster_info!r} with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        try:
            self.results["clusters"][cluster_ip] = {
                "Change_Default_password": "CAN'T VERIFY"
            }

            # Check if password is changed
            try:
                endpoint = "cluster"
                default_pe_session = RestAPIUtil(cluster_ip, user=self.DEFAULT_USERNAME,
                                                 pwd=self.default_pe_password or self.DEFAULT_SYSTEM_PASSWORD,
                                                 port="9440", secured=True)
                cluster_obj = PeCluster(default_pe_session)
                cluster_obj.read(endpoint=endpoint)
            except Exception:
                # if it fails, i.e default password doesn't work, password is changed
                self.results["clusters"][cluster_ip]["Change_Default_password"] = "PASS"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for "
                             f"{cluster_ip}")
