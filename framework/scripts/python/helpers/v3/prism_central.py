from time import sleep
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity
from ..state_monitor.task_monitor import PcTaskMonitor


class PrismCentral(PcEntity):
    kind = "prism_central"
    PC_VM_SPEC = {
        "small": {"num_sockets": 6, "memory_size_in_gb": 26, "data_disk_size_in_gb": 500},
        "large": {"num_sockets": 10, "memory_size_in_gb": 44, "data_disk_size_in_gb": 2500},
        "xlarge": {"num_sockets": 14, "memory_size_in_gb": 60, "data_disk_size_in_gb": 2500}
    }
    PC_VM_SIZE = (1, 3)

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/prism_central"
        super(PrismCentral, self).__init__(session=session)

    # def _is_cmsp_pc(self):
    #     """Checks if it's a CMSP enabled PC.
    #
    #     Returns: True if CMSP enabled PC. False otherwise.
    #     """
    #     svm = (self._svm if hasattr(self, '_svm')
    #            else self._cluster.get_accessible_svm())
    #     if get_resource_type(svm.ip) != ResourceType.PRISM_CENTRAL:
    #         return False
    #
    #     try:
    #         url = ("https://%s:9440/api/iam/authn/.well-known/openid-configuration"
    #                % svm.ip)
    #         resp = HTTP().get(url)
    #         return bool(resp.ok)
    #     except Exception as exc:
    #         ERROR("Failed while determining whether PC is CMSP enabled: %s" % str(exc))
    #         return False

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
            ntp_server_list(list): List of NTP Server IP addresses
            data_disk_size_in_gb(int): The data disk size of the PC VM
            register_to_pe(bool, Optional): Auto register the PE or not. default value is False
            prism_central_service_domain_name (str): This domain name refers to PC services only and is not a FQDN. It is only accessible from within the PC infrastructure.
            cmsp_internal_network (str): This network will be used by the Microservices Infrastructure
            cmsp_subnet_mask (str): subnet mask for the cmsp network
            cmsp_default_gateway (str): default gateway for the cmsp network
            cmsp_ip_address_range (list): [start_ip end_ip] range for the cmsp network

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
                "ntp_server_list": [
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
                "data_disk_size_bytes": pc_config.get("data_disk_size_in_gb") * 1024 * 1024 * 1024,
                "memory_size_bytes": pc_config.get("memory_size_in_gb") * 1024 * 1024 * 1024,
                "dns_server_ip_list": pc_config.get("dns_server_ip_list", []),
                "ntp_server_list": pc_config.get("ntp_server_list", []),
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
                "should_auto_register": pc_config.get("register_to_pe", False),
                "pc_vm_list": pc_vm_list
            }
        }

        if pc_config.get("deploy_cmsp") is True:
            payload["resources"]["cmsp_config"] = {
                "platform_network_configuration": {
                    "subnet_mask": pc_config.get("cmsp_subnet_mask") or "255.255.255.0",
                    "type": pc_config["cmsp_internal_network"],
                    "default_gateway": pc_config.get("cmsp_default_gateway") or "192.168.5.1"
                },
                "pc_domain_name": pc_config["prism_central_service_domain_name"],
                "platform_ip_block_list": pc_config.get("cmsp_ip_address_range") or ["192.168.5.2 192.168.5.64"]
            }

        if pc_config.get("pc_vip"):
            payload["resources"]["virtual_ip"] = pc_config["pc_vip"]

        response = self.create(data=payload)
        if response:
            return response["task_uuid"]

    def enable_cmsp(self, cmsp_subnet_mask: str = "", cmsp_internal_network: str = "", cmsp_default_gateway: str = "",
                    cmsp_ip_address_range: str = "", pc_domain_name: str = "") -> bool:
        """
        Enable CMSP on PC

        Args:
            cmsp_subnet_mask (str): The subnet mask for the CMSP network.
            cmsp_internal_network (str): The internal network to be used by the CMSP.
            cmsp_default_gateway (str): The default gateway for the CMSP network.
            cmsp_ip_address_range (list): The IP address range for the CMSP network.
            pc_domain_name (str): The domain name for the PC services.

        Returns:
            dict: The response from the API call to enable CMSP.
        """
        endpoint = "cmsp/configure"
        payload = self.get_cmsp_config_payload(operation="kEnable",
                                               cmsp_subnet_mask=cmsp_subnet_mask,
                                               cmsp_internal_network=cmsp_internal_network,
                                               cmsp_default_gateway=cmsp_default_gateway,
                                               cmsp_ip_address_range=cmsp_ip_address_range,
                                               pc_domain_name=pc_domain_name)

        response = self.create(endpoint=endpoint, data=payload)
        task_uuid = self.get_task_uuid(response)

        app_response = status = None
        if task_uuid:
            pc_task_monitor = PcTaskMonitor(self.session, task_uuid_list=[task_uuid])
            pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 60
            pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 3600
            try:
                app_response, status = pc_task_monitor.monitor()
            except Exception as e:
                # Perhaps the task container is re-created and the task that we are monitoring is lost. Let's check if
                # CMSP is already enabled.
                sleep(60)


            if app_response:
                raise Exception(f"CMSP Enable Task has failed {app_response}")

            if not status:
                raise Exception(f"Timed out. CMSP Enable Task has not completed in "
                                f"{pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC} seconds")
            return True
        return False

    def validate_cmsp(self, cmsp_subnet_mask: str = "", cmsp_internal_network: str = "", cmsp_default_gateway: str = "",
                    cmsp_ip_address_range: str = "", pc_domain_name: str = "") -> bool:
        """
        Validate CMSP on PC

        Args:
            cmsp_subnet_mask (str): The subnet mask for the CMSP network.
            cmsp_internal_network (str): The internal network to be used by the CMSP.
            cmsp_default_gateway (str): The default gateway for the CMSP network.
            cmsp_ip_address_range (list): The IP address range for the CMSP network.
            pc_domain_name (str): The domain name for the PC services.

        Returns:
            dict: The response from the API call to enable CMSP.
        """
        endpoint = "cmsp/configure"
        payload = self.get_cmsp_config_payload(operation="kValidate",
                                               cmsp_subnet_mask=cmsp_subnet_mask,
                                               cmsp_internal_network=cmsp_internal_network,
                                               cmsp_default_gateway=cmsp_default_gateway,
                                               cmsp_ip_address_range=cmsp_ip_address_range,
                                               pc_domain_name=pc_domain_name)

        response = self.create(endpoint=endpoint, data=payload)
        task_uuid = self.get_task_uuid(response)

        if task_uuid:
            pc_task_monitor = PcTaskMonitor(self.session, task_uuid_list=[task_uuid])
            pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 60
            pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 3600  # 60 mins wait timeout
            app_response, status = pc_task_monitor.monitor()

            if app_response:
                raise Exception(f"CMSP Validation Task has failed {app_response}")

            if not status:
                raise Exception(f"Timed out. CMSP Validation Task has not completed in "
                                f"{pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC} seconds")

            return True
        return False

    @staticmethod
    def get_cmsp_config_payload(operation: str, cmsp_subnet_mask: str = "", cmsp_internal_network: str = "",
                                cmsp_default_gateway: str = "", cmsp_ip_address_range: str = "",
                                pc_domain_name: str = "") -> dict:
        """
        Get CMSP configuration payload
        """
        return {
            "operation": operation,
            "config": {
                "platform_network_configuration": {
                    "subnet_mask": cmsp_subnet_mask or "255.255.255.0",
                    "type": cmsp_internal_network or "kPrivateNetwork",
                    "default_gateway": cmsp_default_gateway or "192.168.5.1"
                },
                "pc_domain_name": pc_domain_name or "prism.cluster.local",
                "platform_ip_block_list": cmsp_ip_address_range or ["192.168.5.2 192.168.5.64"]}
        }
