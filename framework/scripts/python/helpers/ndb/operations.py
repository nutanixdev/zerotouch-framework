from typing import Optional, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..ndb_entity import NDB


class Operation(NDB):

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/operations"
        super(Operation, self).__init__(session)

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

    def upload(
        self,
        source,
        data,
        endpoint="import_file",
        query=None,
        timeout=30,
    ):
        raise NotImplementedError("upload method is not implemented for Auth")

    def list(self, **kwargs):
        """
        Get all the tasks
        Args(kwargs):
          system_triggered(bool): Include system triggered operations
          user_triggered(bool): Include the user triggered operations
          status(int): The status of the operation
          days(int): The operations triggered within days
          from_time(str): The start_time of the tasks
          date_submitted(str): The task submitted time
        Returns:
          list, the list of the operations(tasks)
        """
        query = {
            "hide-subops": "true"
        }
        if kwargs.get("system_triggered", True):
            query.update({
                "system-triggered": "true"
            })
        if kwargs.get("user_triggered"):
            query.update({
                "user-triggered": "true"
            })
        if kwargs.get("status"):
            query.update({
                "status": kwargs.get("status")
            })
        if kwargs.get("days", 1):
            query.update({
                "days": kwargs.get("days", 1)
            })
        if kwargs.get("from_time"):
            query.update({
                "from-time": kwargs.get("from_time")
            })
        if kwargs.get("date_submitted"):
            query.update({
                "date-submitted": kwargs.get("date_submitted")
            })
        if kwargs.get("entity_id"):
            query.update({
                "entity-id": kwargs.get("entity_id")
            })

        # response = super().read(endpoint="short-info", query=query)
        return super().read(endpoint="short-info", query=query, entity_type="operations")
        # return response.get("operations", [])

    def get_operation_by_name(self, name: str, **kwargs) -> Optional[Dict]:
        """
        Get the operation by name
        Args:
          name(str): The name of the operation
        Returns:
          dict: The operation Info
        """
        operations = self.list(**kwargs)
        for operation in operations:
            if operation.get("name") == name:
                return operation
        return None

    def get_operation_by_uuid(self, uuid: str, **kwargs) -> Optional[Dict]:
        """
        Get the operation by name
        Args:
          uuid(str): The name of the operation
        Returns:
          dict: The operation Info
        """
        query = kwargs
        return super().read(endpoint=uuid, query=query)
