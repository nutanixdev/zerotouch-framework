from typing import Optional, Dict
from framework.helpers.v4_api_client import ApiClientV4
from ..pc_batch_op_v4 import PcBatchOpv4

import ntnx_microseg_py_client
import ntnx_microseg_py_client.models.microseg.v4.config as v4MicrosegConfig

class AddressGroup:
    kind = "address-groups"

    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "microseg/v4.0/config/address-groups"
        self.kind = "AddressGroup"
        self.client = v4_api_util.get_api_client("microseg")
        self.address_group_api = ntnx_microseg_py_client.AddressGroupsApi(
            api_client=self.client
            )
        self.batch_op = PcBatchOpv4(v4_api_util, resource_type=self.resource_type, kind=self.kind)

    def list(self):
        return self.address_group_api.list_address_groups().to_dict()

    def get_name_list(self):
        if not self.list()["data"]:
            return []
        else:
            return [ag["name"] for ag in self.list()["data"]]

    def get_uuid_by_name(self, entity_name: Optional[str] = None):
        response = self.address_group_api.list_address_groups(_filter = f"name eq '{entity_name}'")
        if response.data:
            return response.data[0].ext_id
        return ""

    def get_name_uuid_dict(self):
        if not self.list()["data"]:
            return {}
        else:
            return {ag["name"]: ag["ext_id"] for ag in self.list()["data"]}
    
    def get_by_ext_id(self, ext_id):
        return self.address_group_api.get_address_group_by_id(ext_id)

    def delete_address_group_spec(self, ext_id):
        ag_obj = self.get_by_ext_id(ext_id)
        etag = self.client.get_etag(ag_obj.data)
        return ag_obj.data.ext_id, etag

    @staticmethod
    def create_address_group_spec(ag_info) -> Dict:
        address_group = v4MicrosegConfig.AddressGroup.AddressGroup()
        
        address_group.name = ag_info["name"]
        if ag_info.get("description"):
            address_group.description = ag_info["description"]

        if ag_info.get("subnets"):
            address_group.ipv4_addresses = [ntnx_microseg_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                value = subnet["network_ip"],
                prefix_length = subnet["network_prefix"]
            ) for subnet in ag_info["subnets"]]

        if ag_info.get("ranges"):
            address_group.ip_ranges = [v4MicrosegConfig.IPv4Range.IPv4Range(
                start_ip = ip_range["start_ip"],
                end_ip = ip_range["end_ip"]
            ) for ip_range in ag_info["ranges"]]

        return address_group

    def update_address_group_spec(self, ag_info, ag_obj):
        if ag_info.get("new_name"):
            ag_obj.name = ag_info["new_name"]
        if ag_info.get("description"):
            ag_obj.description = ag_info["description"]
        if ag_info.get("subnets"):
            ag_obj.ipv4_addresses = [ntnx_microseg_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                value = subnet["network_ip"],
                prefix_length = subnet["network_prefix"]
            ) for subnet in ag_info["subnets"]]
        if ag_info.get("ranges"):
            ag_obj.ip_ranges = [v4MicrosegConfig.IPv4Range.IPv4Range(
                start_ip = ip_range["start_ip"],
                end_ip = ip_range["end_ip"]
            ) for ip_range in ag_info["ranges"]]
            
        etag = self.client.get_etag(ag_obj)
        return ag_obj, etag
