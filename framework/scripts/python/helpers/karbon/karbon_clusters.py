from copy import deepcopy
from typing import Dict, List, Optional
from framework.helpers.helper_functions import read_creds
from framework.helpers.rest_utils import RestAPIUtil
from .karbon import Karbon
from ..v3.cluster import Cluster
from ..v3.network import Network


class KarbonClusterV1(Karbon):
    kind = "cluster"

    def __init__(self, session: RestAPIUtil, data: Dict):
        self.data = data
        self.name = self.host_os = self.subnet_uuid = self.control_plane_virtual_ip = self.cluster_uuid = \
            self.cluster_type = None
        self.session = session
        self.resource_type = "/v1/k8s/clusters"
        super(KarbonClusterV1, self).__init__(session=session, resource_type=self.resource_type)
        self.build_spec_methods = {
            "name": self._build_spec_name,
            "k8s_version": self._build_spec_k8s_version,
            "cni": self._build_spec_cni,
            "custom_node_configs": self._build_spec_node_configs,
            "storage_class": self._build_spec_storage_class,
        }

    def get_payload(self, cluster_spec: Dict) -> Dict:
        """
        Payload for creating a karbon cluster
        """
        self.name = cluster_spec.get("name")
        self.cluster_type = cluster_spec.get("cluster_type")

        # Get cluster uuid
        cluster_name = cluster_spec.get("cluster", {}).get("name")
        pc_cluster = Cluster(self.session)
        pc_cluster.get_pe_info_list()
        self.cluster_uuid = pc_cluster.name_uuid_map.get(cluster_name)

        # Get subnet uuid
        subnet_name = cluster_spec.get("node_subnet", {}).get("name")
        subnet = Network(self.session)
        self.subnet_uuid = subnet.get_uuid_by_name(cluster_name=cluster_name, subnet_name=subnet_name)

        self.control_plane_virtual_ip = cluster_spec.get("control_plane_virtual_ip")
        self.host_os = cluster_spec.get("host_os")

        spec, error = super(KarbonClusterV1, self).get_spec(params=cluster_spec)
        if error:
            raise Exception(f"Failed generating nke-cluster spec: {error}")

        return spec

    def _get_default_spec(self) -> Dict:
        return deepcopy(
            {
                "name": "",
                "metadata": {"api_version": "v1.0.0"},
                "version": "",
                "cni_config": {},
                "etcd_config": {},
                "masters_config": {"single_master_config": {}},
                "storage_class_config": {},
                "workers_config": {},
            }
        )

    @staticmethod
    def _build_spec_name(payload: Dict, value, complete_config: Optional[Dict] = None) -> (Dict, None):
        payload["name"] = value
        return payload, None

    @staticmethod
    def _build_spec_k8s_version(payload: Dict, value, complete_config: Optional[Dict] = None) -> (Dict, None):
        payload["version"] = value
        return payload, None

    @staticmethod
    def _build_spec_cni(payload: Dict, config: Dict, complete_config: Optional[Dict] = None) -> (Dict, None):
        cni = {
            "node_cidr_mask_size": config["node_cidr_mask_size"],
            "service_ipv4_cidr": config["service_ipv4_cidr"],
            "pod_ipv4_cidr": config["pod_ipv4_cidr"],
        }
        provider = config.get("network_provider")
        if provider == "Calico":
            cni["calico_config"] = {
                "ip_pool_configs": [{"cidr": config["pod_ipv4_cidr"]}]
            }
        elif provider == "Flannel":
            cni["flannel_config"] = {}
        payload["cni_config"] = cni
        return payload, None

    def _build_spec_node_configs(self, payload: Dict, config: Dict,
                                 complete_config: Optional[Dict] = None) -> (Dict, None):
        self.type_is_dev = self.cluster_type != "PROD"
        control_plane_virtual_ip = self.control_plane_virtual_ip
        for key, value in config.items():

            spec_key = "{0}_config".format(key)
            node_pool, err = self._generate_resource_spec(
                value, key if key[-1] != "s" else key[:-1:]
            )
            if err:
                return None, err
            payload[spec_key]["node_pools"] = [node_pool]
            if spec_key == "masters_config":
                if node_pool["num_instances"] > 1:

                    if not control_plane_virtual_ip:
                        err = ("control_plane_virtual_ip is required if the number of master nodes is 2 or "
                               "cluster_type is 'PROD'.")
                        return None, err

                    payload[spec_key].pop("single_master_config")
                    payload[spec_key]["active_passive_config"] = {
                        "external_ipv4_address": control_plane_virtual_ip
                    }

        return payload, None

    def _build_spec_storage_class(self, payload: Dict, config: Dict,
                                  complete_config: Optional[Dict] = None) -> (Dict, None):
        pe_credential = config.get("pe_credential")
        # get credentials from the payload
        try:
            config["pe_username"], config["pe_password"] = (
                read_creds(data=self.data, credential=pe_credential))
        except Exception as e:
            raise Exception(e).with_traceback(e.__traceback__)

        storage_class = {
            "default_storage_class": config.get("default_storage_class"),
            "name": config["name"],
            "reclaim_policy": config.get("reclaim_policy"),
            "volumes_config": {
                "prism_element_cluster_uuid": self.cluster_uuid,
                "username": config.get("pe_username"),
                "password": config.get("pe_password"),
                "storage_container": config["storage_container"],
                "file_system": config.get("file_system"),
                "flash_mode": config.get("flash_mode"),
            },
        }
        payload["storage_class_config"] = storage_class
        return payload, None

    def _generate_resource_spec(self, config: Dict, resource_type: str) -> (Dict, None):

        config, err = self.validate_resources(config, resource_type)
        if err:
            return None, err

        node = {
            "name": "{0}-{1}-pool".format(
                self.name, resource_type
            ),
            "node_os_version": self.host_os,
            "ahv_config": {
                "cpu": config.get("cpu"),
                "memory_mib": config.get("memory_gb") * 1024,
                "disk_mib": config.get("disk_gb") * 1024,
                "network_uuid": self.subnet_uuid,
                "prism_element_cluster_uuid": self.cluster_uuid,
            },
        }
        num_instances = config.get(
            "num_instances",
            1 if self.type_is_dev else 3 if resource_type != "master" else 2,
        )
        node["num_instances"] = num_instances

        return node, None

    # todo need to change this
    @staticmethod
    def validate_resources(resources: Dict, resource_type: str) -> (Optional[Dict], Optional[str]):
        if (
            resource_type == "master"
            and resources.get("num_instances")
            and resources["num_instances"] not in [1, 2]
        ):
            return None, "value of masters.num_instances must be 1 or 2"
        elif (
            resource_type == "etcd"
            and resources.get("num_instances")
            and resources["num_instances"] not in [1, 3, 5]
        ):
            return None, "value of etcd.num_instances must be 1, 3 or 5"
        return resources, None


class KarbonCluster(Karbon):
    kind = "cluster"

    def __init__(self, session: RestAPIUtil):
        self.session = session
        self.resource_type = "/acs/k8s/cluster/"
        super(KarbonCluster, self).__init__(session=session, resource_type=self.resource_type)

    def list(self, **kwargs) -> List:
        return super(KarbonCluster, self).list(data={})
