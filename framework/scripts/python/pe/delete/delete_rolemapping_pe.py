from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v1.authentication import AuthN
from framework.scripts.python.pe.cluster_script import ClusterScript

logger = get_logger(__name__)


class DeleteRoleMappingPe(ClusterScript):
    """
    The Script to delete role mapping in PE clusters
    """
    
    def __init__(self, data: Dict, **kwargs):
        super(DeleteRoleMappingPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        authn = AuthN(pe_session)
        authn_payload = cluster_details.get("directory_services")
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        if not authn_payload.get("ad_name") or not authn_payload.get("role_mappings"):
            self.logger.warning(f"Authentication payload not specified for the cluster {cluster_info!r}")
            return
        try:
            existing_role_mapping = authn.get_role_mappings(directory_name=authn_payload["ad_name"])
            existing_roles = set([(mapping["role"], mapping["entityType"]) for mapping in existing_role_mapping])
            
            for role_mapping in authn_payload["role_mappings"]:
                if (role_mapping.get("role_type"), role_mapping.get("entity_type")) not in existing_roles:
                    self.logger.warning(f"Role {role_mapping['role_type']}-{role_mapping['entity_type']} doesn't exist.")
                    continue

                self.logger.info(f"Deleting role-mapping '{role_mapping['role_type']}-{role_mapping['entity_type']}' in {cluster_info!r}")
                response = authn.delete_role_mapping(
                    directory_name=authn_payload["ad_name"],
                    role_mapping=role_mapping
                )

                if isinstance(response, str):
                    self.exceptions.append(response)
                    continue
        except Exception as e:
            cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"
            self.logger.error(f"{type(self).__name__} failed for the cluster {cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if Role mapping was Deleted / Already not present
        try:
            self.results["clusters"][cluster_ip] = {"Delete_Role_mappings": {}}

            authn_payload = cluster_details.get("directory_services")
            if not authn_payload.get("ad_name") or not authn_payload.get("role_mappings"):
                return

            pe_session = cluster_details["pe_session"]
            authn = AuthN(pe_session)

            existing_role_mappings = []
            existing_roles = set()

            for role_mapping in authn_payload.get("role_mappings"):
                # Initial status
                self.results["clusters"][cluster_ip]["Delete_Role_mappings"][role_mapping["role_type"]] = \
                    "CAN'T VERIFY"

                existing_role_mappings = existing_role_mappings or authn.get_role_mappings(
                    directory_name=authn_payload["ad_name"])
                existing_roles = existing_roles or set([mapping["role"] for mapping in existing_role_mappings])

                if role_mapping.get("role_type") not in existing_roles:
                    self.results["clusters"][cluster_ip]["Delete_Role_mappings"][role_mapping["role_type"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Delete_Role_mappings"][role_mapping["role_type"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(
                f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip!r}")
