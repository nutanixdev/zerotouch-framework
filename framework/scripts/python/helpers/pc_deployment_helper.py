from .v3.prism_central import PrismCentral
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil

logger = get_logger(__name__)


class PCDeploymentUtil:
    """
    PC deployment Helper
    """
    GB = 1024 * 1024 * 1024
    PORT = 9440

    def __init__(self, pe_session: RestAPIUtil):
        self.pe_session = pe_session

    def get_prism_central_vm_size_spec(self, pc_size: str):
        """
        Get the vm spec as per PC size and retuen the vm spec
        Args:
            pc_size(str): pc vm size. Values: small, large, xlarge
        """
        error_message = ""
        try:
            if not self.pc_vm_size_spec(pc_size):
                error_message = f"Failed to get VM Spec for PC Size {pc_size}. Please check the pc size provided. Allowed sizes are: small, large, xlarge."
            return self.pc_vm_size_spec(pc_size), error_message
        except Exception as e:
            logger.error(e)
            error_message = e
            return None, error_message

    def deploy_pc_vm(self, pc_config: dict):
        """
        Deploy the PC VM

        pc_config(dict):
            pc_version(str): The version of the PC
            vm_name_list(list): The list of pc VM names
            ip_list(list): The list of static ip address. The number of IP address
                should be num of VMs + 1
            subnet_mask(str): The subnet mask
            default_gateway(str): The default gateway
            container_uuid(str): The container uuid
            network_uuid(str): The uuid of the network
            num_sockets(int): num of CPU of the PC VM
            memory_size_in_gb(int): The memory size of the PC VM
            dns_server_ip_list(list): List of DNS Server IP addresses
            data_disk_size_in_gb(int): The data disk size of the PC VM
            auto_register(bool, Optional): Auto register the PE or not. default value is False

        example payload:
        {
            "resources": {
            "pc_vm_list": [
                {
                "vm_name": "PC-NameOption-1",
                "container_uuid": "22492f23-16f1-4e10-8982-fe459097759d",
                "num_sockets": 4,
                "data_disk_size_bytes": 536870912000,
                "memory_size_bytes": 17179869184,
                "dns_server_ip_list": [
                    "10.7.3.201"
                ],
                "nic_list": [
                    {
                    "ip_list": [
                        "10.7.248.151"
                    ],
                    "network_configuration": {
                        "network_uuid": "690c7a3a-50b7-4b54-8080-35220323f674",
                        "subnet_mask": "255.255.0.0",
                        "default_gateway": "1.1.1.1"
                    }
                    }
                ]
                }
            ],
            "version": "5.8.1",
            "should_auto_register": False,
            "virtual_ip": "1.1.1.10"
            }
        }

        Returns:
            task_uuid(str): task_uuid of PC VM deployment
        """
        ip_list = pc_config.get("ip_list", [])
        pc_vm_list = []
        vm_name_list = pc_config.pop("vm_name_list")

        container_uuid = pc_config.pop("container_uuid")
        network_uuid = pc_config.pop("network_uuid")
        for i, vm_name in enumerate(vm_name_list):
            pc_vm_config = {
                "vm_name": vm_name,
                "container_uuid": container_uuid,
                "num_sockets": pc_config.get("num_sockets"),
                "data_disk_size_bytes": pc_config.get("data_disk_size_in_gb") * self.GB,
                "memory_size_bytes": pc_config.get("memory_size_in_gb") * self.GB,
                "dns_server_ip_list": pc_config.get("dns_server_ip_list", []),
                "nic_list": [
                {
                    "ip_list": [ip_list[i]],
                    "network_configuration": {
                        "network_uuid": network_uuid,
                        "subnet_mask": pc_config.get("subnet_mask"),
                        "default_gateway": pc_config.get("default_gateway")
                    }
                }
                ]
            }

            pc_vm_list.append(pc_vm_config)

        payload = {
            "resources": {
                "version": pc_config.pop("pc_version"),
                "should_auto_register": pc_config.get("auto_register", False),
                "virtual_ip": pc_config["pc_vip"],
                "pc_vm_list": pc_vm_list
            }
        }

        prism_central_op = PrismCentral(self.pe_session)
        response = prism_central_op.create(data=payload)
        if response:
            logger.debug(response)
            return response["task_uuid"]

    @staticmethod
    def pc_vm_size_spec(size):
        pc_vm_specs = {
            "small": {"num_sockets": 6, "memory_size_in_gb": 26, "data_disk_size_in_gb": 500},
            "large": {"num_sockets": 10, "memory_size_in_gb": 44, "data_disk_size_in_gb": 2500},
            "xlarge": {"num_sockets": 14, "memory_size_in_gb": 60, "data_disk_size_in_gb": 2500}
        }
        return pc_vm_specs.get(size, {})
