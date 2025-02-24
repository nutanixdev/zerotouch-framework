from copy import deepcopy
from typing import Optional
from ..pc_entity_v3 import PcEntity


class ServiceGroup(PcEntity):
    kind = "service_group"

    def __init__(self, module):
        self.resource_type = "/service_groups"
        super(ServiceGroup, self).__init__(module)

    def get_uuid_by_name(self, entity_name: Optional[str] = None, entity_data: Optional[dict] = None, **kwargs):
        kwargs.pop("filter", None)
        filter_criteria = f"name=={entity_name}"
        response = self.list(filter=filter_criteria, **kwargs)
        if response: #added this check to avoid error when response is empty
            for entity in response:
                if entity.get("service_group", {}).get("name") == entity_name:
                    return entity["service_group"]["uuid"]
        return None

    def get_name_list(self):
        service_group_list = self.list()
        name_list =  [
            sg.get("service_group", {}).get("name")
            for sg in service_group_list if sg.get("service_group", {}).get("name")
            ]
        return name_list
    
    def get_name_uuid_dict(self):
        service_group_list = self.list()
        name_uuid_dict = {
            sg.get("service_group", {}).get("name"): sg.get("uuid")
            for sg in service_group_list if sg.get("service_group", {}).get("name")
            }
        return name_uuid_dict

    def create_service_group_spec(self, sg_info):
        spec = self._get_default_spec()
        # Get the name
        self._build_spec_name(spec, sg_info["name"])
        # Get description
        self._build_spec_desc(spec, sg_info.get("description"))

        # Get service_list
        service_details = sg_info.get("service_details", {})
        for protocol, values in service_details.items():
            self._build_spec_service_details(spec, {protocol: values})

        return spec

    def _get_default_spec(self):
        return deepcopy(
            {
                "name": None,
                "is_system_defined": False,
                "service_list": [],
            }
        )

    @staticmethod
    def _build_spec_name(payload, value):
        payload["name"] = value

    @staticmethod
    def _build_spec_desc(payload, value):
        payload["description"] = value

    def _build_spec_service_details(self, payload, config):
        service = None
        if config.get("tcp"):
            service = {"protocol": "TCP"}
            port_range_list = self.generate_port_range_list(config["tcp"])
            service["tcp_port_range_list"] = port_range_list

        if config.get("udp"):
            service = {"protocol": "UDP"}
            port_range_list = self.generate_port_range_list(config["udp"])
            service["udp_port_range_list"] = port_range_list

        if config.get("icmp"):
            service = {"protocol": "ICMP", "icmp_type_code_list": config["icmp"]}
        elif config.get("any_icmp"):
            service = {"protocol": "ICMP", "icmp_type_code_list": []}

        if not service:
            raise Exception("Unsupported Protocol")
        payload["service_list"].append(service)

        return payload, None

    @staticmethod
    def generate_port_range_list(config):
        port_range_list = []
        if "*" not in config:
            for port in config:
                port = port.split("-")
                port_range_list.append(
                    {"start_port": int(port[0]), "end_port": int(port[-1])}
                )
        else:
            port_range_list.append({"start_port": 0, "end_port": 65535})
        return port_range_list
