import json
from typing import List

from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import Entity


class Genesis(Entity):
    __BASEURL__ = "api/nutanix/v1"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/genesis"
        resource_type = self.__BASEURL__ + self.resource_type
        super(Genesis, self).__init__(session=session, resource_type=resource_type)

    def is_karbon_enabled(self) -> List:
        """
        For PC cluster only
        Get the karbon ui service status

        Returns -> list:
          example:
          [false, "Service: KarbonUIService is not enabled."]
          [true, ""]
        """
        json_data = {
            ".oid": "ClusterManager",
            ".method": "is_service_enabled",
            ".kwargs": {"service_name": "KarbonUIService"}
        }
        payload = {"value": json.dumps(json_data)}
        response = self.read(data=payload, method="POST")

        if response.get("value"):
            result = json.loads(response.get("value"))
        else:
            raise Exception("Cannot fetch Karbon status")
        return result.get(".return")

    def enable_karbon(self):
        """
        Enable karbon service
        Returns:
          list: Api response, example
            [true, null]
        """
        json_data = {".oid": "ClusterManager",
                     ".method": "enable_service_with_prechecks",
                     ".kwargs": {
                         "service_list_json":
                             json.dumps({
                                 "service_list": [
                                     "KarbonUIService",
                                     "KarbonCoreService"
                                 ]
                             })
                     }}

        payload = {"value": json.dumps(json_data)}
        response = self.read(data=payload, method="POST")
        if response.get("value"):
            result = json.loads(response.get("value"))
        else:
            raise Exception("Error while enabling Karbon")
        return result.get(".return")

    def list(self, **kwargs):
        raise "Not Implemented"

    def update(self, **kwargs):
        raise "Not Implemented"
