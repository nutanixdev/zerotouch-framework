from copy import deepcopy
from typing import Optional, List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.v4_api_client import ApiClientV4
from ..pc_batch_op_v4 import PcBatchOpv4

import ntnx_microseg_py_client
import ntnx_microseg_py_client.models.microseg.v4.config as v4MicrosegConfig

class ServiceGroup:
    kind = "service-groups"
    # Configure the client
    def __init__(self, v4_api_util: ApiClientV4):
        self.resource_type = "microseg/v4.0/config/service-groups"
        self.kind = "ServiceGroup"
        self.client = v4_api_util.get_api_client("microseg")
        self.service_group_api = ntnx_microseg_py_client.ServiceGroupsApi(
            api_client=self.client
            )
        self.batch_op = PcBatchOpv4(v4_api_util, resource_type=self.resource_type, kind=self.kind)

    def get_uuid_by_name(self, entity_name: Optional[str]):
        response = self.service_group_api.list_service_groups(_filter = f"name eq '{entity_name}'")
        if response.data:
            return response.data[0].ext_id
        return None

    def list(self):
        all_entities = []
        page, limit = 0, 100  # Start at page 0 with the maximum limit

        while True:
            response = self.service_group_api.list_service_groups(_page=page, _limit=limit)
            if not response.data:
                break  # Exit the loop if there are no more entities to fetch
            all_entities.extend(response.data)
            page += 1  # Move to the next page to fetch more entities

        # We use this loop to ensure all entities are retrieved across multiple pages,
        # as the API returns a limited number of records per request.
        
        return all_entities
    
    def get_name_list(self):
        return [sg.name for sg in self.list()]
    
    def get_name_uuid_dict(self):
        return {sg.name: sg.ext_id for sg in self.list()}

    def get_by_ext_id(self, ext_id):
        return self.service_group_api.get_service_group_by_id(ext_id)

    def delete_service_group_spec(self, ext_id):
        sg_obj = self.get_by_ext_id(ext_id)
        etag = self.client.get_etag(sg_obj.data)
        return sg_obj.data.ext_id, etag

    def create_service_group_spec(self, sg_info):
        service_group = v4MicrosegConfig.ServiceGroup.ServiceGroup()
        # Get the name
        service_group.name = sg_info["name"]
        # Get description
        service_group.description = sg_info.get("description")
        # Get service_list
        service_details = sg_info.get("service_details", {})
        self.add_service_details(service_details, service_group)

        return service_group

    def update_service_group_spec(self, sg_info, service_group):
        sg_obj = v4MicrosegConfig.ServiceGroup.ServiceGroup()
        if sg_info.get("new_name"):
            sg_obj.name = sg_info["new_name"]
        else:
            sg_obj.name = sg_info["name"]
        if sg_info.get("description"):
            sg_obj.description = sg_info["description"]
        if sg_info.get("service_details"):
            self.add_service_details(sg_info["service_details"], sg_obj)
        etag = self.client.get_etag(service_group)
        sg_obj.ext_id = service_group.ext_id

        return sg_obj, etag

    @staticmethod
    def add_service_details(service_details, service_group):
        if service_details.get("tcp"):
            service_group.tcp_services = []
            for port in service_details["tcp"]:
                tcp_service = v4MicrosegConfig.TcpPortRangeSpec.TcpPortRangeSpec()
                port = port.split("-")
                tcp_service.start_port = int(port[0])
                tcp_service.end_port = int(port[-1])
                service_group.tcp_services.append(tcp_service)
                

        if service_details.get("udp"):
            service_group.udp_services = []
            for port in service_details["udp"]:
                udp_service = v4MicrosegConfig.UdpPortRangeSpec.UdpPortRangeSpec()
                port = port.split("-")
                udp_service.start_port = int(port[0])
                udp_service.end_port = int(port[-1])
                service_group.udp_services.append(udp_service)

        if service_details.get("any_icmp"):
            service_group.icmp_services = []
            icmp_service = v4MicrosegConfig.IcmpTypeCodeSpec.IcmpTypeCodeSpec()
            icmp_service.is_all_allowed = True
            service_group.icmp_services.append(icmp_service)

        elif service_details.get("icmp"):
            service_group.icmp_services = []
            for icmp in service_details["icmp"]:
                icmp_service = v4MicrosegConfig.IcmpTypeCodeSpec.IcmpTypeCodeSpec()
                icmp_service.type = icmp.get("type")
                icmp_service.code = icmp.get("code")
                service_group.icmp_services.append(icmp_service)
        
