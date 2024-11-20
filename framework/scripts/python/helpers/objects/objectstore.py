from typing import Union, List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..oss_entity_v3 import OssEntityOp
from ..v3.cluster import Cluster as PcCluster
from ..v3.network import Network


class ObjectStore(OssEntityOp):
    """
    Class to handle all the /objectstores REST API endpoints
    """
    ATTRIBUTES = [
        "uuid", "name", "domain", "num_msp_workers", "usage_bytes", "num_buckets",
        "num_objects", "num_alerts_internal", "deployment_version",
        "client_access_network_ip_used_list", "total_capacity_gib",
        "last_completed_step", "state", "percentage_complete", "ipv4_address",
        "num_alerts_critical", "num_alerts_info", "num_alerts_warning",
        "error_message_list", "cluster_name", "client_access_network_name",
        "client_access_network_ip_list", "buckets_infra_network_name",
        "buckets_infra_network_vip", "buckets_infra_network_dns"]
    BUCKET_ATTRIBUTES = [
        "uuid",
        "name",
        "storage_usage_bytes",
        "object_count",
        "versioning",
        "worm",
        "bucket_notification_state",
        "website",
        "retention_start",
        "retention_duration_days",
        "suspend_versioning",
        "cors"
    ]
    kind = "objectstore"
    COMPLETE = "COMPLETE"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/objectstores"
        super(ObjectStore, self).__init__(session=session)

    def get_entity_by_name(self, entity_name: str) -> Union[List, Dict]:
        entities = self.list()

        entity = list(filter(lambda x: x.get("name") == entity_name, entities))
        if entity:
            return entity[0]
        return entity

    def list(self) -> List:
        """
        List the entities by groups call
        Returns:
          list, the list of entity
        """
        return super().list(attributes=self.ATTRIBUTES)

    def get_payload(self, **kwargs) -> Dict:
        """
        Create objectstore
        Args(kwargs):
          name(str): The name of the objectstore
          domain(str): The domain name of the objectstore
          cluster(str): The PE cluster or
          cluster_uuid(str): The PE cluster uuid
          static_ip_list(list): The list static ips, minimal 6 IPs
          storage_network(str): The Storage network name
          (or) storage_network_uuid(str): The uuid of the network, must have IPAM enabled
          public_network(str): The Public network name
          (or) public_network_uuid(str): The uuid of the network, must have IPAM enabled
          num_worker_nodes(int, optional): Number of worker nodes required
          description(str, optional): The description
          num_cpu(int, optional): The num of vCpus for objectstore VMs
          mem_gb(int, optional): The memory in GB for objectstore VMs
          capacity_tb(int, optional): The capacity of the objectstore
        Returns:
          dict, The API response
        """
        static_ip_list = kwargs.get("static_ip_list", [])
        cluster_uuid = kwargs.get("cluster_uuid")
        storage_network_uuid = kwargs.get("storage_network_uuid")
        public_network_uuid = kwargs.get("public_network_uuid")

        if not cluster_uuid:
            if not kwargs.get("cluster"):
                raise Exception("Cluster name has to be passed")
            cluster_obj = PcCluster(session=self.session)
            cluster_uuid = cluster_obj.get_uuid_by_name(kwargs["cluster"])
        network_obj = Network(session=self.session)
        if not storage_network_uuid:
            if not kwargs.get("storage_network") and not kwargs.get("cluster"):
                raise Exception("Storage Network name, Cluster name has to be passed")
            storage_network_uuid = network_obj.get_uuid_by_name(cluster_name=kwargs["cluster"],
                                                                subnet_name=kwargs["storage_network"])
        if not public_network_uuid:
            if not kwargs.get("public_network") and not kwargs.get("cluster"):
                raise Exception("Public Network name, Cluster name has to be passed")
            public_network_uuid = network_obj.get_uuid_by_name(cluster_name=kwargs["cluster"],
                                                               subnet_name=kwargs["public_network"])

        if not cluster_uuid and not storage_network_uuid and not public_network_uuid:
            raise Exception("Invalid Cluster or Network name specified!")

        if len(static_ip_list) < 3:
            raise Exception("Provide at-least 3 static IPs")
        payload = \
            {
                "api_version": "3.0",
                "metadata":
                    {
                        "kind": self.kind
                    },
                "spec":
                    {
                        "name": kwargs.get("name"),
                        "description": kwargs.get("description", ""),
                        "resources": {
                            "domain": kwargs.get("domain"),
                            "num_worker_nodes": kwargs.get("num_worker_nodes", 3),
                            "cluster_reference":
                                {
                                    "kind": "cluster",
                                    "uuid": cluster_uuid
                                },
                            "buckets_infra_network_dns": static_ip_list[0],
                            "buckets_infra_network_vip": static_ip_list[1],
                            "buckets_infra_network_reference":
                                {
                                    "kind": "subnet",
                                    "uuid": storage_network_uuid
                                },
                            "client_access_network_reference": {
                                "kind": "subnet",
                                "uuid": public_network_uuid
                            },
                            "aggregate_resources":
                                {
                                    "total_vcpu_count": 0,
                                    "total_memory_size_mib": 0,
                                    "total_capacity_gib": 0
                                },
                            "client_access_network_ip_list": static_ip_list[2:]}}}
        return payload

    def create(self, **kwargs) -> Dict:
        """
        Create objectstore
        Args(kwargs):
          name(str): The name of the objectstore
          domain(str): The domain name of the objectstore
          cluster(str): The PE cluster
          (or) cluster_uuid(str): The PE cluster uuid
          static_ip_list(list): The list static ips, minimal 6 IPs
          storage_network(str): The Storage network name
          (or) storage_network_uuid(str): The uuid of the network, must have IPAM enabled
          public_network(str): The Public network name
          (or) public_network_uuid(str): The uuid of the network, must have IPAM enabled
          num_worker_nodes(int, optional): Number of worker nodes required
          description(str, optional): The description
          num_cpu(int, optional): The num of vCpus for objectstore VMs
          mem_gb(int, optional): The memory in GB for objectstore VMs
          capacity_tb(int, optional): The capacity of the objectstore
        Returns:
          dict, The API response
        """
        static_ip_list = kwargs.get("static_ip_list", [])
        cluster_uuid = kwargs.get("cluster_uuid")
        storage_network_uuid = kwargs.get("storage_network_uuid")
        public_network_uuid = kwargs.get("public_network_uuid")

        if not cluster_uuid:
            if not kwargs.get("cluster"):
                raise Exception("Cluster name has to be passed")
            cluster_obj = PcCluster(session=self.session)
            cluster_uuid = cluster_obj.get_uuid_by_name(kwargs["cluster"])
        network_obj = Network(session=self.session)
        if not storage_network_uuid:
            if not kwargs.get("storage_network") and not kwargs.get("cluster"):
                raise Exception("Storage Network name, Cluster name has to be passed")
            storage_network_uuid = network_obj.get_uuid_by_name(cluster_name=kwargs["cluster"],
                                                                subnet_name=kwargs["storage_network"])
        if not public_network_uuid:
            if not kwargs.get("public_network") and not kwargs.get("cluster"):
                raise Exception("Public Network name, Cluster name has to be passed")
            public_network_uuid = network_obj.get_uuid_by_name(cluster_name=kwargs["cluster"],
                                                               subnet_name=kwargs["public_network"])

        if not cluster_uuid and not storage_network_uuid and not public_network_uuid:
            raise Exception("Invalid Cluster or Network name specified!")

        if len(static_ip_list) < 3:
            raise Exception("Provide at-least 3 static IPs")
        payload = \
            {
                "api_version": "3.0",
                "metadata":
                    {
                        "kind": self.kind
                    },
                "spec":
                    {
                        "name": kwargs.get("name"),
                        "description": kwargs.get("description", ""),
                        "resources": {
                            "domain": kwargs.get("domain"),
                            "num_worker_nodes": kwargs.get("num_worker_nodes", 3),
                            "cluster_reference":
                                {
                                    "kind": "cluster",
                                    "uuid": cluster_uuid
                                },
                            "buckets_infra_network_dns": static_ip_list[0],
                            "buckets_infra_network_vip": static_ip_list[1],
                            "buckets_infra_network_reference":
                                {
                                    "kind": "subnet",
                                    "uuid": storage_network_uuid
                                },
                            "client_access_network_reference": {
                                "kind": "subnet",
                                "uuid": public_network_uuid
                            },
                            "aggregate_resources":
                                {
                                    "total_vcpu_count": 0,
                                    "total_memory_size_mib": 0,
                                    "total_capacity_gib": 0
                                },
                            "client_access_network_ip_list": static_ip_list[2:]}}}
        return super().create(
            data=payload
        )
