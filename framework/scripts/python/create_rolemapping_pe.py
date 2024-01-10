from typing import Dict
from framework.helpers.log_utils import get_logger
from .helpers.v1.authentication import AuthN
from .cluster_script import ClusterScript

logger = get_logger(__name__)


class CreateRoleMappingPe(ClusterScript):
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

    def __init__(self, data: Dict, **kwargs):
        super(CreateRoleMappingPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        authn = AuthN(pe_session)
        authn_payload = cluster_details.get("directory_services")
        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"

        if not authn_payload.get("ad_name") and not authn_payload.get("role_mappings"):
            self.logger.warning(f"Authentication payload not specified for the cluster "
                                f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'")
            return
        try:
            existing_role_mapping = authn.get_role_mappings(directory_name=authn_payload["ad_name"])
            existing_roles = set([mapping["role"] for mapping in existing_role_mapping])

            for role_mapping in authn_payload["role_mappings"]:
                if role_mapping.get("role_type") in existing_roles:
                    self.logger.warning(f"Role {role_mapping['role_type']} already exists. Skipping...")
                    continue

                self.logger.info(f"Creating new role-mapping '{role_mapping['role_type']}' in {cluster_info}")
                response = authn.create_role_mapping(
                    directory_name=authn_payload["ad_name"],
                    role_mapping=role_mapping
                )

                if isinstance(response, str):
                    self.exceptions.append(response)
                    continue
        except Exception as e:
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            self.logger.error(f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if Role mapping was created/ was already present
        try:
            self.results["clusters"][cluster_ip] = {"Create_Role_mappings": {}}

            authn_payload = cluster_details.get("directory_services")
            if not authn_payload.get("ad_name") and not authn_payload.get("role_mappings"):
                return

            pe_session = cluster_details["pe_session"]
            authn = AuthN(pe_session)

            existing_role_mappings = []
            existing_roles = set()

            for role_mapping in authn_payload.get("role_mappings"):
                # Initial status
                self.results["clusters"][cluster_ip]["Create_Role_mappings"][role_mapping["role_type"]] = \
                    "CAN'T VERIFY"

                existing_role_mappings = existing_role_mappings or authn.get_role_mappings(
                    directory_name=authn_payload["ad_name"])
                existing_roles = existing_roles or set([mapping["role"] for mapping in existing_role_mappings])

                if role_mapping.get("role_type") in existing_roles:
                    self.results["clusters"][cluster_ip]["Create_Role_mappings"][role_mapping["role_type"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Create_Role_mappings"][role_mapping["role_type"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(
                f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
