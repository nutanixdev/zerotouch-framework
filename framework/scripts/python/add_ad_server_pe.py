from helpers.log_utils import get_logger
from scripts.python.cluster_script import ClusterScript
from scripts.python.helpers.v1.authentication import AuthN

logger = get_logger(__name__)


class AddAdServerPe(ClusterScript):
    """
    The Script to add name servers to PE clusters
    """

    def __init__(self, data: dict, **kwargs):
        self._existing_directories = {}
        super(AddAdServerPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        try:
            pe_session = cluster_details["pe_session"]
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"

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

            try:
                self.logger.info(f"Creating new Directory '{authn_payload['ad_name']}'")
                response = authn.create_directory_services(**authn_payload)

                if isinstance(response, str):
                    self.exceptions.append(response)
            except Exception as e:
                self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                       f"with the error: {e}")
                return

            self.logger.info(f"'{authn_payload['ad_name']}' Directory created in the cluster {cluster_info}")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # Check if directory services were created
        for cluster_ip, cluster_details in self.pe_clusters.items():
            try:
                self.results["clusters"][cluster_ip] = {
                    "Create_Directory_services": "CAN'T VERIFY"
                }

                pe_session = cluster_details["pe_session"]
                authn = AuthN(pe_session)
                authn_payload = cluster_details.get("directory_services")

                if not authn_payload:
                    continue

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
