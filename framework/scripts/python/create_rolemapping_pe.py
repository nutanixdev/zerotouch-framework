from helpers.log_utils import get_logger
from scripts.python.helpers.v1.authentication import AuthN
from scripts.python.cluster_script import ClusterScript

logger = get_logger(__name__)


class CreateRoleMapping(ClusterScript):
    """
    The Script to create role mapping in PE clusters
    """
    LOAD_TASK = False
    DEFAULT_ROLE_MAPPINGS = [
        {
            "role_type": "ROLE_CLUSTER_ADMIN",
            "entity_type": "OU",
            "values": ["admin"]
        },
        {
            "role_type": "ROLE_USER_ADMIN",
            "entity_type": "OU",
            "values": ["user"]
        },
        {
            "role_type": "ROLE_CLUSTER_VIEWER",
            "entity_type": "OU",
            "values": ["viewer"]
        }
    ]

    def __init__(self, data: dict, **kwargs):
        super(CreateRoleMapping, self).__init__(data, **kwargs)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        authn = AuthN(pe_session)
        authn_payload = cluster_details.get("directory_services")

        if not authn_payload["ad_name"] and authn_payload["role_mappings"]:
            logger.warning(f"Authentication payload not specified for the cluster "
                           f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
            return
        try:
            authn.create_role_mapping(
                directory_name=authn_payload["ad_name"],
                role_mappings=authn_payload["role_mappings"],
                cluster_info=f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            )
        except Exception as e:
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            logger.error(f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}")
            return

    def verify(self, **kwargs):
        # todo check if verifications is needed?
        pass
