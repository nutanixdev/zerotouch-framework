from copy import deepcopy
from typing import Optional

from .image import Image
from .network import Network
from ..pe_entity_v2 import PeEntityV2
from framework.helpers.rest_utils import RestAPIUtil
from ..v1.container import Container


class HYPERVISOR:
    """
  Hypervisor Constants
  """
    AHV = "AHV"
    ESXI = "ESXI"


class VM(PeEntityV2):
    ON = "on"
    OFF = "off"
    PAUSE = "pause"
    RESUME = "resume"
    SUSPEND = "suspend"
    GUEST_REBOOT = "acpi_reboot"
    GUEST_SHUTDOWN = "acpi_shutdown"
    RESET = "reset"
    POWER_CYCLE = "powercycle"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/vms"
        self.session = session
        super(VM, self).__init__(session=session)
        self.build_spec_methods = {
            "name": self._build_spec_name,
            "description": self._build_spec_description,
            "hypervisor_type": self._build_spec_hypervisor_type,
            "machine_type": self._build_spec_machine_type,
            "timezone": self._build_spec_timezone,
            "memory_mb": self._build_spec_memory_mb,
            "num_vcpus": self._build_spec_num_vcpus,
            "num_cores_per_vcpu": self._build_spec_num_cores_per_vcpu,
            "boot_type": self._build_spec_boot,
            "guest_customization": self._build_spec_guest_customization,
            "boot_disk": self._build_spec_boot_disk,
            "vm_disks": self._build_spec_vm_disks,
            "vm_nics": self._build_spec_vm_nics,
            "agent_vm": self._build_spec_agent_vm,
        }

    @staticmethod
    def _build_spec_name(payload: dict, name: str, complete_config: dict = None) -> (dict, None):
        payload["name"] = name
        return payload, None

    @staticmethod
    def _build_spec_description(payload: dict, description: str, complete_config: dict = None) -> (dict, None):
        payload["description"] = description
        return payload, None

    @staticmethod
    def _build_spec_hypervisor_type(payload: dict, hypervisor_type: str, complete_config: dict = None) -> (dict, None):
        payload["hypervisor_type"] = hypervisor_type
        return payload, None

    @staticmethod
    def _build_spec_machine_type(payload: dict, machine_type: str, complete_config: dict = None) -> (dict, None):
        payload["machine_type"] = machine_type
        return payload, None

    @staticmethod
    def _build_spec_timezone(payload: dict, timezone: str, complete_config: dict = None) -> (dict, None):
        payload["timezone"] = timezone
        return payload, None

    @staticmethod
    def _build_spec_num_vcpus(payload: dict, num_vcpus: int, complete_config: dict = None) -> (dict, None):
        payload["num_vcpus"] = num_vcpus
        return payload, None

    @staticmethod
    def _build_spec_memory_mb(payload: dict, memory_mb: int, complete_config: dict = None) -> (dict, None):
        payload["memory_mb"] = memory_mb
        return payload, None

    @staticmethod
    def _build_spec_num_cores_per_vcpu(payload: dict, num_cores_per_vcpu: int,
                                       complete_config: dict = None) -> (dict, None):
        payload["num_cores_per_vcpu"] = num_cores_per_vcpu
        return payload, None

    @staticmethod
    def _build_spec_boot(payload: dict, boot_type: str, complete_config: dict = None) -> (dict, None):
        payload["boot"] = {
            "boot_type": boot_type,
            "uefi_boot": False
        }
        if boot_type not in ["LEGACY", "SECURE_BOOT"]:
            return None, f"Invalid boot_type {boot_type} specified!"
        if boot_type == "SECURE_BOOT":
            payload["machine_type"] = "Q35"
            payload["uefi_boot"] = True
        else:
            # Default order is applied. TODO: Ability to provide the boot priority
            payload["boot"]["boot_device_order_list"] = ["CDROM", "DISK", "NETWORK"]
        return payload, None

    @staticmethod
    def _build_spec_guest_customization(payload: dict, guest_customization: dict,
                                        complete_config: dict = None) -> (dict, None):
        payload["vm_customization_config"] = {
            # "files_to_inject_list": [],
            "userdata": guest_customization["user_data"]
        }

        if guest_customization.get("files_to_inject_list"):
            payload["vm_customization_config"]["files_to_inject_list"] = guest_customization["files_to_inject_list"]
        return payload, None

    @staticmethod
    def _build_spec_agent_vm(payload: dict, agent_vm: bool, complete_config: dict = None) -> (dict, None):
        payload["vm_features"] = {
            "agent_vm": agent_vm
        }
        return payload, None

    @staticmethod
    def _get_vm_disk_spec(clone_disk: bool = False, create_disk: bool = False) -> dict:
        vm_disk_spec = {
            "is_cdrom": bool,
            "is_empty": bool,
            "disk_address": {
                "device_bus": str,
                "device_index": int
            },
        }
        if clone_disk:
            vm_disk_spec["vm_disk_clone"] = {
                "disk_address": {
                    "vmdisk_uuid": str
                },
                "minimum_size": int
            }
        if create_disk:
            vm_disk_spec["vm_disk_create"] = {
                "size": int,
                "storage_container_uuid": str
            }

        return deepcopy(vm_disk_spec)

    def _build_spec_boot_disk(self, payload: dict, boot_disk: dict, complete_config: dict = None) -> (dict, None):
        boot_disk_config = self._get_vm_disk_spec(clone_disk=True)
        boot_disk_config["is_cdrom"] = boot_disk.get("is_cdrom", False)
        boot_disk_config["is_empty"] = boot_disk.get("is_empty", False)
        boot_disk_config["disk_address"] = {
            "device_bus": boot_disk.get("device_bus", "SCSI"),
            "device_index": 0
        }

        image_name = boot_disk["vm_disk_clone"]["image"]
        image_op = Image(session=self.session)
        vm_disk_info = image_op.get_vm_disk_info_by_name(image_name)
        vmdisk_uuid = image_op.get_vm_disk_id(vm_disk_info=vm_disk_info)
        vm_disk_size = image_op.get_vm_disk_size(vm_disk_info=vm_disk_info)
        boot_disk_config["vm_disk_clone"]["disk_address"]["vmdisk_uuid"] = vmdisk_uuid
        boot_disk_config["vm_disk_clone"]["minimum_size"] = vm_disk_size * 1048576
        payload["vm_disks"] = [boot_disk_config] + payload["vm_disks"]
        return payload, None

    def _build_spec_vm_disks(self, payload: dict, vm_disks: list, complete_config: dict = None) -> (dict, None):
        for disk in vm_disks:
            if not disk.get("vm_disk_clone") and not disk.get("vm_disk_create"):
                raise Exception(f"Invalid operation specified!")
            clone_disk = bool(disk.get("vm_disk_clone"))
            create_disk = bool(disk.get("vm_disk_create"))
            disk_config = self._get_vm_disk_spec(clone_disk=clone_disk, create_disk=create_disk)
            disk_config["is_cdrom"] = disk.get("is_cdrom", False)
            disk_config["is_empty"] = disk.get("is_empty", False)
            disk_config["disk_address"] = {
                "device_bus": disk.get("device_bus", "SCSI"),
                "device_index": len(payload["vm_disks"])
            }
            if clone_disk:
                image_name = disk["vm_disk_clone"]["image"]
                image_op = Image(session=self.session)
                vm_disk_info = image_op.get_vm_disk_info_by_name(image_name)
                vmdisk_uuid = image_op.get_vm_disk_id(vm_disk_info=vm_disk_info)
                vm_disk_size = image_op.get_vm_disk_size(vm_disk_info=vm_disk_info)
                disk_config["vm_disk_clone"]["disk_address"]["vmdisk_uuid"] = vmdisk_uuid
                disk_config["vm_disk_clone"]["minimum_size"] = vm_disk_size * 1048576
            elif create_disk:
                disk_config["vm_disk_create"]["size"] = disk["vm_disk_create"]["size_mib"] * 1048576
                storage_container_uuid = (Container(session=self.session).
                                          get_uuid_by_name(disk["vm_disk_create"]["storage_container"]))
                disk_config["vm_disk_create"]["storage_container_uuid"] = storage_container_uuid
            payload["vm_disks"].append(disk_config)
        return payload, None

    @staticmethod
    def _get_vm_nic_spec() -> dict:
        return deepcopy({
            "network_uuid": str,
            # "is_connected": bool,
            # "is_primary": bool,
            # "mac_address": str,
            # "ip_endpoint_list": list
        })

    def _build_spec_vm_nics(self, payload: dict, vm_nics: list, complete_config: dict = None) -> (dict, None):
        for nic in vm_nics:
            nic_config = self._get_vm_nic_spec()

            network_uuid = Network(session=self.session).get_uuid_by_name(nic["network"])
            nic_config["network_uuid"] = network_uuid

            if nic.get("ip_endpoint_list", []):
                nic_config["ip_endpoint_list"] = nic.get("ip_endpoint_list")
            elif nic.get("static_ip"):
                nic_config["requested_ip_address"] = nic["static_ip"]
            else:
                nic_config.pop("ip_endpoint_list")
            payload["vm_nics"].append(nic_config)
        return payload, None

    @staticmethod
    def _get_default_spec():
        return deepcopy(
            {
                "name": "",
                "memory_mb": 1024,
                "num_vcpus": 1,
                "num_cores_per_vcpu": 1,
                "boot": dict(),
                "vm_disks": [],
                "vm_nics": []
            }
        )

    def power_transition(self, vm_uuid: str, transition: str) -> dict:
        endpoint = f"{vm_uuid}/set_power_state"
        data = {
            "transition": transition
        }
        return self.create(data=data, endpoint=endpoint)

    def get_vm_info(self, vm_name_list: list) -> list[dict]:
        vm_name_list = ",".join([f"vm_name=={vm_name}" for vm_name in vm_name_list])
        query = {
            "filter": f"{vm_name_list}"
        }
        return self.read(query=query)

    def get_ipv4(self, vm_name_list: Optional[list] = None, ip_addresses: Optional[list] = None) -> Optional[str]:
        """
        When there are more than one IPv4 address, return the IP starting with
        "10" if there is one otherwise return any other IP.
        This will be primarily used in ssh_uvm
        Returns:
          str: IPv4 address
        """
        ipv4 = None
        if not ip_addresses:
            if not vm_name_list:
                raise ValueError("Either vm_name_list or ip_addresses should be provided!")
            vm_info_list = self.get_vm_info(vm_name_list)
            ip_addresses = [vm_info["ip_addresses"] for vm_info in vm_info_list if vm_info.get("ip_addresses")]

        for ip in ip_addresses:
            if not ip:
                continue
            # For ESX cluster, the IP address would be something like 10.7.1.138/16
            # We should remove the net mask part.
            ip = ip.split("/")[0].strip()
            # store valid IPv4 address
            ipv4 = ip
            # if IP starts with "10" return it.
            if ipv4.startswith("10"):
                return ipv4

            # If IP starting with 10 is not found return any other valid ipv4 address
        return ipv4
