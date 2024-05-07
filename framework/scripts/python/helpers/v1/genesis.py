import json
from typing import List
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Genesis(PeEntityV1):
    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/genesis"
        super(Genesis, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

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

    def is_fc_enabled(self) -> List:
        """
        For PC cluster only
        Get the FC service status

        Returns -> list:
          example:
          [false, "Service: FoundationCentralService is not enabled."]
          [true, ""]
        """
        json_data = {
            ".oid": "ClusterManager",
            ".method": "is_service_enabled",
            ".kwargs": {"service_name": "FoundationCentralService"}
        }
        payload = {"value": json.dumps(json_data)}
        response = self.read(data=payload, method="POST")

        if response.get("value"):
            result = json.loads(response.get("value"))
        else:
            raise Exception("Cannot fetch Foundation Central status")
        return result.get(".return")

    def enable_karbon(self) -> List:
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

    def enable_fc(self):
        """
        Enable FC service
        Returns:
          list: Api response, example
            [true, null]
        """
        json_data = {".oid": "ClusterManager",
                     ".method": "enable_service",
                     ".kwargs": {
                         "service_list_json":
                             json.dumps({
                                 "service_list": [
                                     "FoundationCentralService"
                                 ]
                             })
                     }}

        payload = {"value": json.dumps(json_data)}
        response = self.read(data=payload, method="POST")
        if response.get("value"):
            result = json.loads(response.get("value"))
        else:
            raise Exception("Error while enabling Foundation Central")
        return result.get(".return")

    def list(self, **kwargs):
        raise "Not Implemented"

    def update(self, **kwargs):
        raise "Not Implemented"
