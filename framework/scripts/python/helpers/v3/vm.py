from ..pc_entity import PcEntity
from framework.helpers.rest_utils import RestAPIUtil


class VmPowerState(object):
    """
    The class to define Vm power state
    """
    ON = "ON"
    OFF = "OFF"


class VM(PcEntity):
    kind = "vm"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/vms"
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
