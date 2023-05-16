from helpers.log_utils import get_logger
from scripts.python.cluster_script import ClusterScript
from scripts.python.helpers.v1.authentication import AuthN

logger = get_logger(__name__)


class AddAdServerPe(ClusterScript):
    """
    The Script to add name servers to PE clusters
    """

    def __init__(self, data: dict, **kwargs):
        super(AddAdServerPe, self).__init__(data, **kwargs)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        try:
            pe_session = cluster_details["pe_session"]

            authn = AuthN(pe_session)
            authn_payload = cluster_details.get("directory_services")

            if not authn_payload:
                logger.warning(f"Authentication payload not specified for the cluster "
                               f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
                return

            existing_directory_services = authn.get_directories()
            ad = next((ad for ad in existing_directory_services
                       if ad.get("name") == authn_payload["ad_name"]), None)

            if ad:
                logger.warning(f"{authn_payload['ad_name']} already exists in the cluster "
                               f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
                return

            try:
                response = authn.create_directory_services(**authn_payload)

                if isinstance(response, str):
                    self.exceptions.append(response)
            except Exception as e:
                cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
                self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                       f"with the error: {e}")
                return

            logger.info(f"{authn_payload['ad_name']} created in the cluster "
                        f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        # todo check if verifications is needed?
        pass
