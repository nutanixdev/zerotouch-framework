from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.authentication import AuthN

logger = get_logger(__name__)


class DeleteAdServerPe(ClusterScript):
    """
    The Script to delete Active Directory in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(DeleteAdServerPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"
        try:
            pe_session = cluster_details["pe_session"]

            authn = AuthN(pe_session)
            authn_payload = cluster_details.get("directory_services")

            if not authn_payload:
                self.logger.warning(f"Authentication payload not specified for the cluster {cluster_info!r}")
                return

            existing_directory_services = authn.get_directories()
            ad = next((ad for ad in existing_directory_services
                       if ad.get("name") == authn_payload["ad_name"]), None)

            if not ad:
                self.logger.warning(f"{authn_payload['ad_name']!r} Directory doesn't exist in the cluster"
                                    f"{cluster_info!r}")
                return

            self.logger.info(f"Deleting Directory {authn_payload['ad_name']!r}")
            response = authn.delete_directory_services(authn_payload['ad_name'])

            if isinstance(response, str):
                self.exceptions.append(response)
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info!r} "
                                   f"with the error: {e}")

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if directory services were deleted/ never existed
        try:
            authn_payload = cluster_details.get("directory_services")

            if not authn_payload:
                return

            self.results["clusters"][cluster_ip] = {
                "Delete_Directory_services": "CAN'T VERIFY"
            }

            pe_session = cluster_details["pe_session"]
            authn = AuthN(pe_session)

            existing_directory_services = authn.get_directories()
            directory_services_name_list = [ad["name"] for ad in existing_directory_services]

            if authn_payload["ad_name"] not in directory_services_name_list:
                self.results["clusters"][cluster_ip]["Delete_Directory_services"] = "PASS"
            else:
                self.results["clusters"][cluster_ip]["Delete_Directory_services"] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} "
                             f"for {cluster_ip}")
