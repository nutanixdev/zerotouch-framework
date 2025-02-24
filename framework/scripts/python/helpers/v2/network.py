from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..v1.virtual_switch import VirtualSwitch
from ..pe_entity_v2 import PeEntityV2


class Network(PeEntityV2):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/networks"
        self.session = session
        super(Network, self).__init__(session=session)

    def create(self, **kwargs):
        data = self.get_json_for_create(**kwargs)
        return super(Network, self).create(data=data)

    def get_uuid_by_name(self, name: str) -> str:
        networks = self.read()
        for network in networks:
            if network.get("name") == name:
                return network.get("uuid")
        raise ValueError(f"Network with name {name} not found!")

    def get_json_for_create(self, **kwargs) -> Dict:
        """
        Create PE Network Payload
        Args:
          **kwargs:
            name (str) : Name of the Network
            vlan_id (int): Vlan ID
            virtual_switch (str): Virtual switch name
            ip_config (dict):
                network_ip (str): Network ip, eg 192.168.10.0
                prefix_length (int): Prefix length, eg, 24
                default_gateway_ip (str): Default gateway ip, eg, 192.168.10.1
                pool_list (list): list of dicts with ip ranges, eg,
                    [ {"range": "192.168.10.20 192.168.10.250"}]
                dhcp_server_address: If unspecified, DHCP server IP will be the
                    highest unalloted unicast address in the subnet

        Returns:
          dict

        Example Payload:
        {
            "name": "vlan-113",
            "vlan_id": 113,
            "ip_config": {
                "network_address": "1.1.1.0",
                "prefix_length": 24,
                "default_gateway": "1.1.1.1",
                "dhcp_options": {
                    "domain_name": "eng.company",
                    "domain_name_servers": "10.10.10.10,20.20.20.20",
                    "domain_search": "eng.company,eng.local"
                },
                "pool": [
                    {
                        "range": "1.1.1.10 1.1.1.20"
                    }
                ]
            }
        }

        Example Response: {"networkUuid":"7dde0c68-846c-4b76-b4df-b32713258c9a"}
        """
        name = kwargs.get("name")
        vlan_id = kwargs.get("vlan_id", None)
        ip_config = kwargs.get("ip_config", {})
        virtual_switch = kwargs.get("virtual_switch", "")

        payload = {
                "name": name,
                "vlan_id": vlan_id
        }

        if vlan_id:
            payload["vlan_id"] = vlan_id

        if virtual_switch is not None:
            vs = VirtualSwitch(session=self.session)
            virtual_switch_uuid = vs.get_vs_uuid(name=virtual_switch)
            payload["virtual_switch_uuid"] = virtual_switch_uuid
        if ip_config:
            if ip_config.get("dhcp_options").get("domain_name_server_list"):
                ip_config["dhcp_options"]["domain_name_servers"] = \
                    ",".join(ip_config["dhcp_options"].pop("domain_name_server_list"))

            if ip_config.get("dhcp_options").get("domain_search_list"):
                ip_config["dhcp_options"]["domain_search"] = \
                    ",".join(ip_config["dhcp_options"].pop("domain_search_list"))

            ip_config = {
                "network_address": ip_config["network_ip"],
                "prefix_length": ip_config["network_prefix"],
                "default_gateway": ip_config["default_gateway_ip"],
                "dhcp_options": ip_config.get("dhcp_options", {}),
                "pool": ip_config.get("pool_list", [])
            }

            if ip_config.get("dhcp_server_address"):
                ip_config["dhcp_server_address"] = {"ip": ip_config["dhcp_server_address"]}
            payload["ip_config"] = ip_config
        return payload
