from ..pc_entity_v3 import PcEntity
from .image import Image
from .network import Network
from ..v3.cluster import Cluster as PcCluster
from framework.helpers.rest_utils import RestAPIUtil


class VmPowerState(object):
    """
    The class to define Vm power state
    """
    ON = "ON"
    OFF = "OFF"


class VM(PcEntity):
    kind = "vm"
    MACHINE_TYPE = "Q35"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/vms"
        self.pc_session = session
        super(VM, self).__init__(session)

    def batch_create_vm(self, vm_create_payload_list: list):
        return self.batch_op.batch_create(request_payload_list=vm_create_payload_list)

    def get_uuid_by_name(self, cluster_name: str, vm_name: str, **kwargs) -> str:
        filter_criteria = f"cluster_name=={cluster_name};vm_name=={vm_name}"
        kwargs["filter"] = filter_criteria
        return super(VM, self).get_uuid_by_name(vm_name, **kwargs)

    def batch_power_on_vm(self, vm_payload_list: list):
        updated_payload_list = []
        for vm_info in vm_payload_list:
            vm_info['spec']['resources']['power_state'] = VmPowerState.ON
            updated_payload_list.append(vm_info)
        return self.batch_op.batch_update(updated_payload_list)
    
    def batch_delete_vm(self, uuid_list: list):
        return self.batch_op.batch_delete(entity_list=uuid_list)

    def create_pc_vm_payload(self, **kwargs):
        """
        Create a config spec for v3 API.
        Args(kwargs):
            name(str): Name of the VM
            include_cdrom(bool): if we need to include cdrom in the vm create
            num_vcpus(int, optional): num of vCPUs, The default value is 1.
            memory_mb(int, optional): Memory size in MB. Default value is 1024
            power_state(str): Power State of the VM, eg "ON" , "OFF". Default value is OFF
            image_list(str): List of images
            hardware_clock_timezone(str): Default time zone 'UTC'
            network_list(str): List of NIC to be added
            cluster_name(str): Cluster name where the VM needs to be created
            ip_endpoint_list(list): list of ip_endpoints
            guest_customization(dict): encoded guest customization dict
                                    either sysprep or cloud-init
        Returns:
            dict: The vm config spec
        """
        cluster_name = kwargs["cluster_name"]
        payload = self.get_pc_vm_payload()

        # Create list disks & cdrom to be added
        device_index = 0
        disk_list = []
        if kwargs.get("include_cdrom"):
            cdrom_config = {
            "device_properties": {
                "device_type": "CDROM",
                "disk_address": {
                "adapter_type": "IDE",
                "device_index": 0
                }
            }
            }
            disk_list.append(cdrom_config)
            device_index += 1

        # List of imaged to be added
        if kwargs.get("image_list"):
            image_obj = Image(self.pc_session)
            for image in kwargs["image_list"]:
                image_uuid = image_obj.get_uuid_by_name(image)
                if not image_uuid:
                    raise Exception(f"Image {image} not found in cluster {cluster_name}")
                disk_list.append(self.create_disk_spec_from_image(image_uuid=image_uuid,
                                                                  device_index=device_index))
                device_index += 1
        payload["resources"]["disk_list"] = disk_list

        # NIC to be added. For now supporting only one NIC addition
        # TODO: support multiple NICs for a VM
        if kwargs.get("network"):
            nic_list = []
            network_obj = Network(self.pc_session)
            network_uuid = network_obj.get_uuid_by_name(cluster_name=cluster_name,
                                                        subnet_name=kwargs["network"])
            if not network_uuid:
                raise Exception(f"Network {kwargs['network']} not found in cluster {cluster_name}")
            nic_list.append({"subnet_reference": {"uuid": network_uuid, "kind": "subnet"}})
            payload["resources"]["nic_list"] = nic_list

        # Update VM resouce specs
        payload["resources"]["num_vcpus_per_socket"] = kwargs.pop("num_vcpus_per_socket", 1)
        payload["resources"]["num_sockets"] = kwargs.pop("num_vcpus", 1)
        payload["resources"]["memory_size_mib"] = kwargs.pop("memory_mb", 1024)
        payload["resources"]["power_state"] = kwargs.pop("power_state", "OFF")

        # Updating boot config
        boot_type = kwargs.get("boot_type", "LEGACY")
        payload["resources"]["boot_config"] = {"boot_type": boot_type}
        if boot_type == "SECURE_BOOT":
            payload["resources"]["machine_type"] = self.MACHINE_TYPE
            if kwargs.get("hardware_virtualization_enabled"):
                payload["resources"]["hardware_virtualization_enabled"] = True
        if boot_type == "LEGACY":
            # Default order is applied.
            # TODO: Ability to provide the boot priority
            payload["resources"]["boot_config"]["boot_device_order_list"]: ["CDROM", "DISK", "NETWORK"]

        # Update Cluster uuid
        cluster_obj = PcCluster(session=self.session)
        cluster_uuid = cluster_obj.get_uuid_by_name(cluster_name)
        if not cluster_uuid:
            raise Exception(f"Invalid Cluster name {cluster_name} specified!")
        payload["cluster_reference"] = {"uuid": cluster_uuid, "kind": "cluster"}

        # TODO: Enhance ip_endpoint_list when multi NICs are supported
        if kwargs.get("ip_endpoint_list", None):
            payload["resources"]["nic_list"][0]["ip_endpoint_list"] = kwargs.get("ip_endpoint_list")

        if kwargs.get("guest_customization", None):
            payload["resources"]["guest_customization"] = kwargs.get("guest_customization")

        return payload

    @staticmethod
    def create_disk_spec_from_image(image_uuid, device_index=0):
        """
        Create the disk spec from image. Usually this is used to create a boot disk.
        Args:
            image_uuid(str): The uuid of the image
            device_index(int): the device index of the disk
        Returns:
            dict: The disk spec
        """
        return {
            "device_properties": {
            "device_type": "DISK",
            "disk_address": {
                "adapter_type": "SCSI", "device_index": device_index}},
            "data_source_reference": {
            "kind": "image",
            "uuid": image_uuid}}

    @staticmethod
    def get_pc_vm_payload():
        {
            "metadata": {
                "categories_mapping": {},
                "kind": "vm",
            },
            "spec": {
                "name": "test-payload",
                "resources": {
                    "memory_overcommit_enabled": False,
                    "num_sockets": 1,
                    "memory_size_mib": 2048,
                    "num_vcpus_per_socket": 1,
                    "hardware_clock_timezone": "UTC",
                    "disk_list": [],  
                    "gpu_list": [],
                    "boot_config": {
                        "boot_type": "LEGACY",
                        "boot_device_order_list": [
                            "CDROM",
                            "DISK",
                            "NETWORK"
                        ]
                    },
                    "guest_customization": {},
                    "nic_list": []
                },
                "cluster_reference": {}
            },
            "api_version": "3.1.0"
        }
    @staticmethod
    def _get_vm_ip_address(vm_info):
        ip_addresses = []
        for nic in vm_info["status"]["resources"].get("nic_list", {}):
            ip_endpoint_list = nic.get("ip_endpoint_list", [])
            for endpoint in ip_endpoint_list:
                if endpoint.get("ip"):
                    ip_addresses.append(endpoint["ip"])
        return ip_addresses

    @staticmethod
    def _filter_vm_by_uuid(vm_list, uuid_list):
        new_vm_list = []
        for vm in vm_list:
            if vm["metadata"]["uuid"] in uuid_list:
                new_vm_list.append(vm)
        return new_vm_list
