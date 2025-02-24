from typing import Optional, Dict, Union, List
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class Auth(NDB):
    DEFAULT_ERA_PASSWORD = "Nutanix.123"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/auth"
        super(Auth, self).__init__(session)

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
        query=None,
        use_base_url=False,
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

    def update_password(self, new_password: str = DEFAULT_ERA_PASSWORD):
        """
        Reset the password of the ERA cluster
        Args:
          new_password(str): The new password to set
        Returns:
          dict: API response, for example:
            {"status":"success", "message":"Password updated successfully"}

        """
        endpoint = "update"
        query = {
            "accept-eula": True
        }
        payload = {"password": new_password}
        return super().create(endpoint=endpoint, data=payload, query=query)
