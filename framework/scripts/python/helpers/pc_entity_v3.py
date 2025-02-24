import json
from copy import deepcopy
from typing import Optional
from framework.helpers.rest_utils import RestAPIUtil
from .entity import Entity
from .pc_batch_op import PcBatchOp


class PcEntity(Entity):
    __BASEURL__ = "api/nutanix/v3"
    resource_type = ""
    kind = ""
    V3_LIST_CHUNKSIZE = 500

    def __init__(self, session: RestAPIUtil, **kwargs):
        resource_type = self.__BASEURL__ + self.resource_type
        self.batch_op = PcBatchOp(session, resource_type=self.resource_type, kind=self.kind)
        super(PcEntity, self).__init__(session=session, resource_type=resource_type)

    def list(self, **kwargs):
        payload = {
            "kind": kwargs.pop("kind", self.kind),
            "offset": kwargs.pop("offset", 0),
            "filter": kwargs.pop("filter", ""),
            "length": kwargs.pop("length", self.V3_LIST_CHUNKSIZE),
            "sort_order": kwargs.pop("sort_order", None),
            "sort_attribute": kwargs.pop("sort_attribute", None)
        }
        if payload["length"] > self.V3_LIST_CHUNKSIZE:
            length = payload["length"]
            payload["length"] = self.V3_LIST_CHUNKSIZE
            resp = {self.entity_type: []}
            while True and payload["offset"] <= length:
                sub_resp = super(PcEntity, self).list(data=payload, **kwargs)
                if not sub_resp:
                    break
                resp[self.entity_type].extend(sub_resp)
                payload["offset"] += self.V3_LIST_CHUNKSIZE
            return resp[self.entity_type]

        return super(PcEntity, self).list(data=payload, **kwargs)

    def get_entity_by_name(self, entity_name: str, **kwargs):
        entities = self.list(**kwargs)

        for entity in entities:
            if entity.get("spec", {}).get("name"):
                name = entity["spec"]["name"]
            elif entity.get("status", {}).get("name"):
                name = entity["status"]["name"]
            elif entity.get("info", {}).get("name"):
                name = entity["info"]["name"]
            else:
                continue
            if name == entity_name:
                return entity
        return None

    def get_uuid_by_name(self, entity_name: Optional[str] = None, entity_data: Optional[dict] = None, **kwargs):
        if not entity_data:
            if not entity_name:
                raise Exception("Entity name is needed to get the UUID")
            entity_data = self.get_entity_by_name(entity_name, **kwargs)
        if not entity_data:
            return None
        return entity_data["metadata"]["uuid"]

    def reference_spec(self):
        return deepcopy(
            {
                "kind": self.kind,
                "uuid": ""
            }
        )

    @staticmethod
    def get_task_uuid(api_response: dict) -> str:
        """
        Parse the api response to get the Task uuid
        Args:
          api_response(Dict): api response
        Returns:
          str : uuid
        """
        task_uuid = None
        # todo bug
        # sometimes api_response in str
        if isinstance(api_response, str):
            try:
                api_response = json.loads(api_response)
            except Exception as e:
                raise (Exception(f"Cannot get task uuid from the response: {api_response}: {e}")
                       .with_traceback(e.__traceback__))

        if api_response and api_response.get('status', {}).get('execution_context', {}).get('task_uuid'):
            task_uuid = api_response['status']['execution_context']['task_uuid']
        # In some cases only task_uuid is returned in response
        elif api_response and api_response.get('task_uuid', {}):
            task_uuid = api_response["task_uuid"]

        if not task_uuid:
            raise Exception(f"Cannot get task uuid from the response: {api_response}")

        return task_uuid
