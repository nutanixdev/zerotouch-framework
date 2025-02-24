from typing import Optional
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity


class AvailabilityZone(PcEntity):
    kind = "availability_zone"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/availability_zones"
        self.session = session
        super(AvailabilityZone, self).__init__(session=session)

    def get_mgmt_url_by_name(self, entity_name: Optional[str] = None, **kwargs) -> str:
        filter_criteria = f"name=={entity_name}"
        kwargs["filter"] = filter_criteria
        entity = super(AvailabilityZone, self).get_entity_by_name(entity_name, **kwargs)
        if not entity:
            raise Exception(f"AZ with name {entity_name} doesn't exist!")
        mgmt_url = str(entity.get("status", {}).get("resources", {}).get("management_url"))
        if not mgmt_url:
            raise Exception("Couldn't fetch mgmt url")
        return mgmt_url
