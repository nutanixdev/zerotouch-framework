from copy import deepcopy
from typing import Optional, List, Dict
from framework.helpers.v4_api_client import ApiClientV4
from ..pc_batch_op_v4 import PcBatchOpv4

import ntnx_networking_py_client
import ntnx_networking_py_client.models.networking.v4.config as v4NetworkingConfig



class VPC:
    kind = "vpcs"

    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "networking/v4.0/config/vpcs"
        self.kind = "VPC"
        self.client = v4_api_util.get_api_client("network")
        self.v4_api_util = v4_api_util
        self.vpcs_api = ntnx_networking_py_client.VpcsApi(
            api_client=self.client
            )
        self.batch_op = PcBatchOpv4(v4_api_util, resource_type=self.resource_type, kind=self.kind)

    def list(self):
        return self.vpcs_api.list_vpcs().to_dict()

    def get_name_list(self):
        return [vpc["name"] for vpc in self.list()["data"]]

    def get_uuid_by_name(self, entity_name: Optional[str] = None) -> str:
        response = self.vpcs_api.list_vpcs(_filter = f"name eq '{entity_name}'")
        if response.data:
            return response.data[0].ext_id
        return None

    def get_name_uuid_dict(self):
        return {vpc["name"]: vpc["ext_id"] for vpc in self.list()["data"]}
    
    def get_by_ext_id(self, ext_id):
        return self.vpcs_api.get_vpc_by_id(ext_id)

    def delete_vpc_spec(self, ext_id):
        vpc_obj = self.get_by_ext_id(ext_id)
        etag = self.client.get_etag(vpc_obj.data)
        return vpc_obj.data.ext_id, etag

    @staticmethod
    def create_vpc_spec(vpc_info) -> Dict:
        vpc = v4NetworkingConfig.Vpc.Vpc()
        
        vpc.name = vpc_info["name"]
        if vpc_info.get("description"):
            vpc.description = vpc_info["description"]
        if vpc_info.get("type"):
            vpc.vpc_type = getattr(v4NetworkingConfig.VpcType.VpcType, vpc_info["type"])
        if vpc_info.get("dns"):
            vpc.common_dhcp_options = v4NetworkingConfig.VpcDhcpOptions.VpcDhcpOptions(
                domain_name_servers = [
                    ntnx_networking_py_client.models.common.v1.config.IPAddress.IPAddress(
                        ipv4 = ntnx_networking_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                            value = dns.split("/")[0],
                            prefix_length = (int(dns.split("/")[1]))
                        )
                    ) for dns in vpc_info["dns"]
                ]
            )
        if vpc_info.get("routable_ips"):
            vpc.externally_routable_prefixes = []
            for routable_ip in vpc_info["routable_ips"]:
                vpc.externally_routable_prefixes.append(v4NetworkingConfig.IPSubnet.IPSubnet(
                    ipv4 = v4NetworkingConfig.IPv4Subnet.IPv4Subnet(
                        ip = ntnx_networking_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                            value = routable_ip.split("/")[0]
                        ),
                        prefix_length = int(routable_ip.split("/")[1])
                    )
                ))
            
        return vpc

    def update_vpc_spec(self, vpc_info, vpc_object):
        if vpc_info.get("new_name"):
            vpc_object.name = vpc_info["new_name"]
        if vpc_info.get("description"):
            vpc_object.description = vpc_info["description"]

        if vpc_info.get("dns"):
            vpc_object.common_dhcp_options = v4NetworkingConfig.VpcDhcpOptions.VpcDhcpOptions(
                domain_name_servers = [
                    ntnx_networking_py_client.models.common.v1.config.IPAddress.IPAddress(
                        ipv4 = ntnx_networking_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                            value = dns.split("/")[0],
                            prefix_length = (int(dns.split("/")[1]))
                        )
                    ) for dns in vpc_info["dns"]
                ]
            )
        if vpc_info.get("routable_ips"):
            vpc_object.externally_routable_prefixes = []
            for routable_ip in vpc_info["routable_ips"]:
                vpc_object.externally_routable_prefixes.append(v4NetworkingConfig.IPSubnet.IPSubnet(
                    ipv4 = v4NetworkingConfig.IPv4Subnet.IPv4Subnet(
                        ip = ntnx_networking_py_client.models.common.v1.config.IPv4Address.IPv4Address(
                            value = routable_ip.split("/")[0]
                        ),
                        prefix_length = int(routable_ip.split("/")[1])
                    )
                ))

        etag = self.v4_api_util.get_api_client("microseg").get_etag(vpc_object)
        return vpc_object, etag
