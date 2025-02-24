from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class AuthDirectory(NDB):

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/authdirectory"
        super(AuthDirectory, self).__init__(session)

    def get_spec(self, params: Optional[Dict] = None, spec: Optional[dict] = None) -> (Optional[Dict], Optional[str]):
        raise NotImplementedError(f"get_spec method is not implemented for  {type(self).__name__}")

    def update(
        self,
        data=None,
        endpoint=None,
        query=None,
        timeout=None,
        method="PUT"
    ):
        raise NotImplementedError(f"update method is not implemented for  {type(self).__name__}")

    def delete(
        self,
        uuid=None,
        timeout=None,
        endpoint=None,
        query=None,
    ):
        raise NotImplementedError(f"delete method is not implemented for  {type(self).__name__}")

    def read(
        self,
        uuid=None,
        method="GET",
        data=None,
        headers=None,
        endpoint=None,
        query=None,
        timeout=None,
        entity_type=None,
        custom_filters=None
    ):
        raise NotImplementedError(f"read method is not implemented for  {type(self).__name__}")

    def list(
        self,
        endpoint=None,
        use_base_url=False,
        query=None,
        data=None,
        custom_filters=None,
        timeout=None,
        entity_type=None
    ) -> Union[List, Dict]:
        raise NotImplementedError("list method is not implemented for Auth")

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        raise NotImplementedError("upload method is not implemented for Auth")

    def configure_active_directory(self, name: str, domain: str, url: str, service_account_username: str,
                                   service_account_password: str):
        """
        Configure Active Directory
        Args:
          name(str): The name of the directory
          domain(str): The domain of the directory
          url(str): The url of the directory
          service_account_username(str): The service account username
          service_account_password(str): The service account password
        """
        payload = {
            "directoryName": name,
            "directoryType": "activeDirectory",
            "searchType": "recursive",
            "directoryURL": url,
            "domain": domain,
            "serviceAccountUsername": service_account_username,
            "serviceAccountPassword": service_account_password
        }
        return super().create(data=payload)
