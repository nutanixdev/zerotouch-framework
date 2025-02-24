from copy import deepcopy
from typing import Optional, List, Dict
from ..pc_entity_v3 import PcEntity


class AddressGroup(PcEntity):
    kind = "address_group"

    def __init__(self, module):
        self.resource_type = "/address_groups"
        super(AddressGroup, self).__init__(module)

    def get_uuid_by_name(self, entity_name: Optional[str] = None, entity_data: Optional[dict] = None, **kwargs) -> str:
        kwargs.pop("filter", None)
        filter_criteria = f"name=={entity_name}"
        response = self.list(filter=filter_criteria, **kwargs)
        #edited the method to access UUID from the nested address_group dict
        for entity in response:
            if entity.get("address_group", {}).get("name") == entity_name:
                return entity["address_group"]["uuid"]
        return None
    
    def get_name_list(self):
        return [entity.get("address_group", {}).get("name") for entity in self.list()]

    def create_address_group_spec(self, ag_info) -> Dict:
        spec = self._get_default_spec()
        # Get the name
        self._build_spec_name(spec, ag_info["name"])
        # Get description
        self._build_spec_desc(spec, ag_info.get("description"))
        # Get ip_address_block_list
        self._build_spec_subnets(spec, ag_info.get("subnets", []))
        return spec

    def _get_default_spec(self) -> Dict:
        return deepcopy({
            "name": None,
            "description": "",
            "ip_address_block_list": []
        })

    @staticmethod
    def _build_spec_name(payload, name):
        payload["name"] = name

    @staticmethod
    def _build_spec_desc(payload, desc):
        payload["description"] = desc

    def _build_spec_subnets(self, payload, subnets: List):
        ip_address_block_list = []
        for subnet in subnets:
            ip_address_block_list.append(
                self._get_ip_address_block(
                    subnet["network_ip"], subnet["network_prefix"]
                )
            )
        payload["ip_address_block_list"] = ip_address_block_list

    @staticmethod
    def _get_ip_address_block(ip: str, prefix: str) -> Dict:
        spec = {"ip": ip, "prefix_length": prefix}
        return spec
