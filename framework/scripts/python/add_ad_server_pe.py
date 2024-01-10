from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .cluster_script import ClusterScript
from .helpers.v1.authentication import AuthN

logger = get_logger(__name__)


class AddAdServerPe(ClusterScript):
    """
    The Script to add Active Directory in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(AddAdServerPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
        try:
            pe_session = RestAPIUtil(cluster_ip, user="admin",
                                     pwd=cluster_details['admin_pe_password'],
                                     port="9440", secured=True) \
                if cluster_details.get('admin_pe_password') else cluster_details["pe_session"]

            authn = AuthN(pe_session)
            authn_payload = cluster_details.get("directory_services")

            if not authn_payload:
                self.logger.warning(f"Authentication payload not specified for the cluster {cluster_info}")
                return

            existing_directory_services = authn.get_directories()
            ad = next((ad for ad in existing_directory_services
                       if ad.get("name") == authn_payload["ad_name"]), None)

            if ad:
                self.logger.warning(f"'{authn_payload['ad_name']}' Directory already exists in the cluster"
                                    f" {cluster_info}")
                return

            self.logger.info(f"Creating new Directory '{authn_payload['ad_name']}'")
            response = authn.create_directory_services(**authn_payload)

            if isinstance(response, str):
                self.exceptions.append(response)
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                   f"with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if directory services were created
        try:
            authn_payload = cluster_details.get("directory_services")

            if not authn_payload:
                return

            self.results["clusters"][cluster_ip] = {
                "Create_Directory_services": "CAN'T VERIFY"
            }

            pe_session = cluster_details["pe_session"]
            authn = AuthN(pe_session)

            existing_directory_services = authn.get_directories()
            directory_services_name_list = [ad["name"] for ad in existing_directory_services]

            if authn_payload["ad_name"] in directory_services_name_list:
                self.results["clusters"][cluster_ip]["Create_Directory_services"] = "PASS"
            else:
                self.results["clusters"][cluster_ip]["Create_Directory_services"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' "
                             f"for {cluster_ip}")
