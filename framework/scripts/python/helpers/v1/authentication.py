from typing import List
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class AuthN(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/authconfig"
        self.session = session
        super(AuthN, self).__init__(session=session)

    def create_directory_services(self, **ad_params):
        endpoint = "directories"
        spec = {
            "name": ad_params["ad_name"],
            "domain": ad_params["ad_domain"],
            "directoryUrl": "ldap://{}:389".format(ad_params["ad_server_ip"]),
            "groupSearchType": ad_params.get("group_search_type", "NON_RECURSIVE"),
            "directoryType": ad_params["directory_type"],
            "connectionType": "LDAP",
            "serviceAccountUsername": ad_params["service_account_username"],
            "serviceAccountPassword": ad_params["service_account_password"]
        }
        return self.create(data=spec, endpoint=endpoint, timeout=360)

    def get_directories(self):
        endpoint = "directories"
        return self.read(endpoint=endpoint)

    def create_role_mapping(self, directory_name: str, role_mappings: List, cluster_info: str):
        endpoint = f"directories/{directory_name}/role_mappings"
        existing_role_mapping = self.read(endpoint=endpoint)

        existing_role = set([mapping["role"] for mapping in existing_role_mapping])
        for role_mapping in role_mappings:
            if role_mapping.get("role_type") not in existing_role:
                spec = {
                    "directoryName": directory_name,
                    "role": role_mapping["role_type"],
                    "entityType": role_mapping["entity_type"],
                    "entityValues": role_mapping["values"]
                }
                response = self.create(data=spec, endpoint=endpoint)
                if isinstance(response, str):
                    raise Exception(response)
                logger.info(f"Created Role Mapping type '{role_mapping['role_type']}' in the cluster {cluster_info}")
            else:
                logger.warning(f"Role Mapping '{role_mapping['role_type']}' already exists in the cluster {cluster_info}")
