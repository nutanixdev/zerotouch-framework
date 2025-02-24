from typing import List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity


class Network(PcEntity):
    kind = "subnet"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/subnets"
        self.session = session
        super(Network, self).__init__(session=session)

    def batch_create_network(self, subnet_create_payload_list: List):
        return self.batch_op.batch_create(request_payload_list=subnet_create_payload_list)

    def batch_delete_network(self, uuid_list: List):
        return self.batch_op.batch_delete(entity_list=uuid_list)

    def get_uuid_by_name(self, cluster_name: str, subnet_name: str, **kwargs) -> str:
        filter_criteria = f"cluster_name=={cluster_name};name=={subnet_name}"
        kwargs["filter"] = filter_criteria
        return super(Network, self).get_uuid_by_name(subnet_name, **kwargs)

    @staticmethod
    def create_subnet_payload(**kwargs) -> Dict:
        """
        Create Subnet Payload
        Args:
          **kwargs:
            name (str) : Name of the subnet
            subnet_type (str): VLAN (PC) or OVERLAY (Xi)
            vlan_id (int): Vlan ID (PC)
            subnet_ip (str): Subnet ip, eg 192.168.10.0
            vpc_id (str): the vpc id for subnet
            prefix_length (int): Prefix length, eg, 24
            default_gateway_ip (str): Default gateway ip, eg, 192.168.10.1
            pool_list (list): list of dicts with ip ranges, eg,
                [ {"range": "192.168.10.20 192.168.10.250"}]
            cluster_uuid (str) : Cluster uuid
            virtual_network_reference (dict): Virtual Network reference (Xi)
              eg,  {"kind": "virtual_network",
              "uuid": "773d9dfd-aa48-44b0-a502-60f25d002576"}
            is_external (bool): True to enable - "External Connectivity for VPCs"
                                Defaults to False.

        Returns:
          dict
        """
        name = kwargs.get("name")
        subnet_type = kwargs.get("subnet_type", "VLAN")
        vlan_id = kwargs.get("vlan_id", None)
        vs_uuid = kwargs.get("vs_uuid", None)
        vpc_id = kwargs.get("vpc_id", None)
        ip_config = kwargs.get("ip_config", {})
        cluster_uuid = kwargs.get("cluster_uuid", None)
        # virtual_network_reference = kwargs.get("virtual_network_reference", {})
        is_external = kwargs.get("is_external", False)
        enable_nat = kwargs.get("enable_nat", True)

        payload = {
            "spec": {
                "name": name,
                "resources": {
                    "subnet_type": subnet_type,
                    "ip_config": {}
                }
            },
            "metadata": {
                "kind": "subnet",
                "name": name
            },
            "api_version": "3.1.0"
        }

        if vlan_id:
            payload["spec"]["resources"].update({"vlan_id": vlan_id})

        if vs_uuid is not None:
            payload["spec"]["resources"].update({"virtual_switch_uuid": vs_uuid})

        if vpc_id:
            payload["spec"]["resources"].update(
                {
                    "vpc_reference": {
                        "kind": "vpc",
                        "uuid": vpc_id
                    }})
            payload["spec"]["resources"].update(
                {
                    "virtual_network_reference": {
                        "kind": "virtual_network",
                        "uuid": vpc_id
                    }})
        elif subnet_type == "OVERLAY":
            # todo need to implement
            pass

        if is_external:
            payload["spec"]["resources"].update({"is_external": is_external})

        if not enable_nat:
            payload["spec"]["resources"].update({"enable_nat": enable_nat})

        if cluster_uuid:
            payload["spec"].update(
                {
                    "cluster_reference": {
                        "kind": "cluster",
                        "uuid": cluster_uuid
                    }
                })

        if ip_config:
            ip_config = {
                "subnet_ip": ip_config["network_ip"],
                "prefix_length": ip_config["network_prefix"],
                "default_gateway_ip": ip_config["default_gateway_ip"],
                "dhcp_options": ip_config.get("dhcp_options", {}),
                "pool_list": ip_config.get("pool_list", [])
            }

            if ip_config.get("dhcp_server_address"):
                ip_config["dhcp_server_address"] = {"ip": ip_config["dhcp_server_address"]}
            payload["spec"]["resources"]["ip_config"] = ip_config
        return payload

    def create_pc_subnet_payload(self, **kwargs) -> Dict:
        """
        Build subnet create payload for PC
        Args:
          **kwargs:
            name (str) : Name of the subnet
            vlan_id (int): Vlan ID (PC)
            subnet_ip (str): Subnet ip, eg 192.168.10.0
            prefix_length (int): Prefix length, eg, 24
            default_gateway_ip (str): Default gateway ip, eg, 192.168.10.1
            pool_list (list): list of dicts with ip ranges, eg,
                [ {"range": "192.168.10.20 192.168.10.250"}]
            cluster_uuid (str) : Cluster UUID

        Returns:
          dict
        """
        return self.create_subnet_payload(**kwargs)
