from typing import List, Dict, Union
from framework.helpers.rest_utils import RestAPIUtil
from ..entity import Entity


class IamProxyObjects(Entity):
    """
    Class to handle all the /iam_proxy REST API endpoints
    """
    # For all the OSS REST API call, we need to pass the base_path
    kind = "iam_proxy"

    def __init__(self, session: RestAPIUtil):
        resource_type = "/iam_proxy"
        base_url = "oss"
        super(IamProxyObjects, self).__init__(session=session, resource_type=base_url+resource_type)

    def list_directory_services(self) -> Dict:
        """
        Get all directory services
        Returns:
          list
        """
        return self.read(endpoint="directory_services")

    def get_by_domain_name(self, domain_name: str) -> Union[List, Dict]:
        """
        Get directory service by domain name
        Args:
          domain_name(str): the domain name
        Returns:
          list
        """
        entities = self.list_directory_services()
        entity = list(filter(lambda x: x["spec"]["resources"]["domain_name"] == domain_name, entities))
        if entity:
            return entity[0]
        return entity

    def add_directory_service(self, ad_name: str, ad_domain: str, ad_directory_url: str, service_account_username: str,
                              service_account_password: str) -> Dict:
        """
        Add directory service to objects
          ad_name(str): The name of directory service
          ad_domain(str): The domain name
          ad_directory_url(str): The ip address of the domain
          service_account_username(str): The username
          service_account_password(str): The password
        Returns:
          dict: The API response
        """
        if ad_domain not in service_account_username:
            service_account_username = f"{service_account_username}@{ad_domain}"

        payload = \
            {
                "api_version": "3.1.0",
                "metadata": {"kind": "directory_service"},
                "spec":
                    {
                        "name": ad_name,
                        "resources":
                            {
                                "domain_name": ad_domain,
                                "directory_type": "ACTIVE_DIRECTORY",
                                "url": ad_directory_url,
                                "service_account":
                                    {
                                        "username": service_account_username,
                                        "password": service_account_password
                                    }
                            }
                    }
            }
        return self.create(
            endpoint="directory_services",
            data=payload
        )

    def create_ad_users(self, idp_id: str, usernames: List) -> Dict:
        """
        Create AD users
        Args(kwargs):
          usernames(list): list of usernames, without domain name, for example
            ["user1", "user2"]
          idp_id(str): The uuid of the directory service
        Returns:
          dict: API response
        """

        usernames = usernames or []
        payload = {
            "users": [
                {
                    "type": "ldap",
                    "username": username,
                    "display_name": username.split("@")[0],
                    "idp_id": idp_id
                }
                for username in usernames]}

        return self.create(
            data=payload,
            endpoint="buckets_access_keys"
        )

    def list_users(self) -> List[Dict]:
        """
        Get all the OSS users
        Returns:
          list
        """
        response = self.read(endpoint="users")
        if response.get("length") < response.get("total_matches"):
            query = f"length={response.get('total_matches')}"
            response = self.read(endpoint="users", query=query)
        return [entity for entity in response.get("users")]
