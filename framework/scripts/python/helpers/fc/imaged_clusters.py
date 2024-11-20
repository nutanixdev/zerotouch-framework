from copy import deepcopy
from typing import List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..fc_entity import FcEntity

__metaclass__ = type


class ImagedCluster(FcEntity):
    entity_type = "imaged_clusters"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/imaged_clusters"
        super(ImagedCluster, self).__init__(session, self.resource_type)
        self.build_spec_methods = {
            "cluster_external_ip": self._build_spec_cluster_exip,
            "common_network_settings": self._build_spec_common_network_settings,
            "hypervisor_isos": self._build_spec_hypervisor_iso_details,
            "storage_node_count": self._build_spec_storage_node_count,
            "redundancy_factor": self._build_spec_redundancy_factor,
            "cluster_name": self._build_spec_cluster_name,
            "aos_package_url": self._build_spec_aos_package_url,
            "cluster_size": self._build_spec_cluster_size,
            "aos_package_sha256sum": self._build_spec_aos_package_sha256sum,
            "timezone": self._build_spec_timezone,
            "nodes_list": self._build_spec_nodes_list,
            "skip_cluster_creation": self._build_spec_skip_cluster_creation,
            "filters": self._build_spec_filters,
        }

    def _get_default_spec(self):
        return deepcopy(
            {
                "cluster_external_ip": "",
                "common_network_settings": {},
                "redundancy_factor": 2,
                "cluster_name": "",
                "aos_package_url": None,
                "hypervisor_isos": [],
                "nodes_list": [],
            }
        )

    def _build_spec_cluster_exip(self, payload, value):
        payload["cluster_external_ip"] = value

        return payload, None

    def _build_spec_storage_node_count(self, payload, value):
        payload["storage_node_count"] = value
        return payload, None

    def _build_spec_redundancy_factor(self, payload, value):
        payload["redundancy_factor"] = value
        return payload, None

    def _build_spec_cluster_name(self, payload, value):
        payload["cluster_name"] = value
        return payload, None

    def _build_spec_aos_package_url(self, payload, value):
        payload["aos_package_url"] = value
        return payload, None

    def _build_spec_cluster_size(self, payload, value):
        payload["cluster_size"] = value
        return payload, None

    def _build_spec_aos_package_sha256sum(self, payload, value):
        payload["aos_package_sha256sum"] = value
        return payload, None

    def _build_spec_timezone(self, payload, value):
        payload["timezone"] = value
        return payload, None

    def _build_spec_skip_cluster_creation(self, payload, value):
        payload["skip_cluster_creation"] = value
        return payload, None

    def _build_spec_common_network_settings(self, payload, nsettings):
        net = self._get_default_network_settings(nsettings)
        payload["common_network_settings"] = net
        return payload, None

    def _build_spec_hypervisor_iso_details(self, payload, value):
        payload["hypervisor_isos"] = value
        return payload, None

    def _build_spec_nodes_list(self, payload, node_details):
        nodes_list = []
        for node in node_details:
            spec = self._get_default_nodes_spec(node)
            nodes_list.append(spec)
        payload["nodes_list"] = node_details
        return payload, None

    def _build_spec_filters(self, payload, value):
        payload["filters"] = value
        return payload, None

    def _get_default_hypervisor_iso_details(self, isodetails):
        spec = {}
        default_spec = {
            "hyperv_sku": None,
            "url": None,
            "hypervisor_type": None,
            "hyperv_product_key": None,
            "sha256sum": None,
        }
        for k in default_spec:
            v = isodetails.get(k)
            if v:
                spec[k] = v
        return spec

    def _get_default_network_settings(self, cnsettings):
        spec = {}
        default_spec = {
            "cvm_dns_servers": [],
            "hypervisor_dns_servers": [],
            "cvm_ntp_servers": [],
            "hypervisor_ntp_servers": [],
        }

        for k in default_spec:
            v = cnsettings.get(k)
            if v:
                spec[k] = v
        return spec

    def _get_default_nodes_spec(self, node):
        spec = {}
        default_spec = {
            "cvm_gateway": None,
            "ipmi_netmask": None,
            "rdma_passthrough": False,
            "imaged_node_uuid": None,
            "cvm_vlan_id": None,
            "hypervisor_type": None,
            "image_now": True,
            "hypervisor_hostname": None,
            "hypervisor_netmask": None,
            "cvm_netmask": None,
            "ipmi_ip": None,
            "hypervisor_gateway": None,
            "hardware_attributes_override": {},
            "cvm_ram_gb": None,
            "cvm_ip": None,
            "hypervisor_ip": None,
            "use_existing_network_settings": False,
            "ipmi_gateway": None,
        }

        for k in default_spec:
            if k in node:
                v = node.get(k)
                if v:
                    spec[k] = v
        return spec

    # Helper function
    @staticmethod
    def get_aos_ahv_spec(imaging_params: Dict) -> Dict:
        """Update hypervisor iso details

        Args:
            imaging_params (dict): Imaging parameters
                aos_url: "https://aos-url-path"
                hypervisor_type: "kvm"
                hypervisor_url: "https://ahv-url-path"

        Returns:
            dict: Return Imaging dict that will be used in FC deployment payload
        """
        return {
            "aos_package_url": imaging_params["aos_url"],
            "hypervisor_isos": [{
                "hypervisor_type": imaging_params["hypervisor_type"],
                "url": imaging_params["hypervisor_url"]
            }] if imaging_params.get("hypervisor_url") else []
        }

    # Helper function
    def update_node_details(self, node_detail_list: list, cluster_info: Dict) -> List:
        """Update the node details with the given parameters

        Args:
            node_detail_list (list): List of node details to update
            cluster_info (Dict): Cluster information

        Returns:
            List: List of updated node details
        """
        updated_node_list = []
        for node in node_detail_list:
            if not cluster_info.get("use_existing_network_settings", cluster_info["use_existing_network_settings"]):
                node_spec = {
                    "rdma_passthrough": cluster_info.get("rdma_passthrough", False),
                    "hypervisor_type": cluster_info["imaging_parameters"]["hypervisor_type"],
                    "image_now": cluster_info.get("re-image", False),
                    "cvm_ram_gb": cluster_info.get("cvm_ram", 12),
                    "use_existing_network_settings": False
                }
                if cluster_info.get("cvm_vlan_id"):
                    node_spec["cvm_vlan_id"] = cluster_info["cvm_vlan_id"]
            else:
                node_spec = {
                    "use_existing_network_settings": True,
                    "imaged_node_uuid": node["imaged_node_uuid"],
                    "image_now": cluster_info.get("re-image", False),
                    }
            node.update(node_spec)
            updated_node_list.append(node)
        return updated_node_list

    # Helper function
    def create_fc_deployment_payload(self, cluster_info: Dict, existing_node_detail_dict: List):
        """Create FC Deployment Payload for each cluster

        Args:
            cluster_info (Dict): Cluster information provided in the input file
            existing_node_detail_dict (List): Exsiting node details for the given cluster info

        Returns:
            (list, str): (List of node details, Error Message)
        """
        cluster_data = {
            "cluster_external_ip": cluster_info.get("cluster_vip", ""),
            "redundancy_factor": cluster_info["redundancy_factor"],
            "cluster_name": cluster_info["cluster_name"],
            "cluster_size": cluster_info["cluster_size"],
            "common_network_settings": {
                "cvm_dns_servers": cluster_info["dns_servers"],
                "hypervisor_dns_servers": cluster_info["dns_servers"],
                "cvm_ntp_servers": cluster_info["ntp_servers"],
                "hypervisor_ntp_servers": cluster_info["ntp_servers"],
            }
        }
        cluster_data["nodes_list"] = self.update_node_details(existing_node_detail_dict, cluster_info)
        if cluster_info.get("re-image", False):
            cluster_data.update(self.get_aos_ahv_spec(cluster_info["imaging_parameters"]))
        return cluster_data, None
