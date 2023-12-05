from typing import Dict, List
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class AuthN(PeEntityV1):
    """
    v1 version of Auth
    """
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/authconfig"
        self.session = session
        super(AuthN, self).__init__(session=session)

    def create_directory_services(self, **ad_params) -> Dict:
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
        return self.create(data=spec, endpoint=endpoint)

    def get_directories(self) -> List:
        endpoint = "directories"
        return self.read(endpoint=endpoint)

    def get_role_mappings(self, directory_name: str) -> Dict:
        endpoint = f"directories/{directory_name}/role_mappings"
        return self.read(endpoint=endpoint)

    def create_role_mapping(self, directory_name: str, role_mapping: Dict) -> Dict:
        endpoint = f"directories/{directory_name}/role_mappings"

        spec = {
            "directoryName": directory_name,
            "role": role_mapping["role_type"],
            "entityType": role_mapping["entity_type"],
            "entityValues": role_mapping["values"]
        }
        return self.create(data=spec, endpoint=endpoint)
