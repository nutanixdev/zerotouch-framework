from copy import deepcopy
from typing import Optional
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.entity import Entity
from scripts.python.helpers.pc_batch_op import PcBatchOp


class PcEntity(Entity):
    __BASEURL__ = "api/nutanix/v3"
    resource_type = ""
    kind = ""
    V3_LIST_CHUNKSIZE = 250

    def __init__(self, session: RestAPIUtil, **kwargs):
        resource_type = self.__BASEURL__ + self.resource_type
        self.batch_op = PcBatchOp(session, base_url=self.__BASEURL__, resource_type=self.resource_type, kind=self.kind, **kwargs)
        super(PcEntity, self).__init__(session=session, resource_type=resource_type)

    def list(self, **kwargs):
        payload = {
            "kind": kwargs.pop("kind", self.kind),
            "offset": kwargs.pop("offset", 0),
            "filter": kwargs.pop("filter", ""),
            "length": kwargs.pop("length", self.V3_LIST_CHUNKSIZE)
        }
        return super(PcEntity, self).list(data=payload, **kwargs)

    def get_entity_by_name(self, entity_name: str, **kwargs):
        entities = self.list(**kwargs)

        for entity in entities:
            if entity.get("spec", {}).get("name"):
                name = entity["spec"]["name"]
            elif entity.get("status", {}).get("name"):
                name = entity["status"]["name"]
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
