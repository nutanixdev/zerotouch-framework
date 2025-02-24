from copy import deepcopy
from time import sleep
from typing import Dict
from framework.scripts.python.pe.other_ops.register_pe_to_pc import RegisterToPc
from framework.scripts.python.helpers.v1.multicluster import MultiCluster
from framework.scripts.python.helpers.v2.cluster import Cluster as ClusterV2
from framework.scripts.python.helpers.v3.prism_central import PrismCentral
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.container import Container
from framework.scripts.python.helpers.v2.network import Network
from framework.scripts.python.helpers.v2.vm import VM
from framework.scripts.python.helpers.cvm.ssh_cvm import SSHCvm
from framework.scripts.python.helpers.state_monitor.task_monitor import PcTaskMonitor as TaskMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import read_creds, create_pc_objects

logger = get_logger(__name__)


class DeployPC(ClusterScript):
    """
    This class is used to deploy Prism Central (PC) in a Nutanix environment (PE).

    Attributes:
        DEFAULT_USERNAME (str): Default username for the Prism Central.
        DEFAULT_SYSTEM_PASSWORD (str): Default password for the Prism Central.

    Methods:
        __init__(self, data: Dict, **kwargs): Initializes the DeployPC object with the provided data.
        execute_single_cluster(self, cluster_ip: str, cluster_details: dict): Deploys Prism Central in a single cluster.
        upload_pc_software(self, cvm_ip: str, cvm_username: str, cvm_password: str, pc_config: dict): Downloads and uploads PC software to PE.
        verify_single_cluster(self, cluster_ip: str, cluster_details: Dict): Verifies if the deployed PC is accessible.
        check_cluster_vip_access(self, cluster_vip: str): Checks if the Cluster VIP is accessible.
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        """
        Initializes the DeployPC object with the provided data.

        Args:
            data (Dict): A dictionary containing the data for the DeployPC object.
            **kwargs: Arbitrary keyword arguments.
        """
        self.data = data
        super(DeployPC, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        """
        Deploys Prism Central in a single cluster.

        Args:
            cluster_ip (str): The IP address of the cluster.
            cluster_details (dict): A dictionary containing the details of the cluster.
        """
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']!r}" if (
            'name' in cluster_details['cluster_info']) else f"{cluster_ip!r}"
        pe_session = cluster_details["pe_session"]

        # Deploy PC in the cluster
        try:
            if deploy_pc_configs := cluster_details.get("pc_configs"):
                if self.parallel:
                    self.set_current_thread_name(cluster_ip)
                pc_obj = PrismCentral(pe_session)

                # get Cluster UUIDs
                if not cluster_details.get("cluster_info", {}).get("uuid"):
                    cluster = ClusterV2(pe_session)
                    cluster.get_cluster_info()
                    cluster_details["cluster_info"].update(cluster.cluster_info)

                for deploy_pc_config in deploy_pc_configs:
                    try:
                        self.logger.info(f"Deploying PC {deploy_pc_config['pc_vm_name_prefix']!r} in the cluster:"
                                         f" {cluster_info}")

                        if deploy_pc_config.get("check_existing_pc", True):
                            # Check if PE is already registered to PC
                            cluster = MultiCluster(pe_session)
                            pc_ip = cluster.get_pc_ip()
                            if pc_ip:
                                self.logger.warning(
                                    f"Cluster {cluster_ip!r} is already registered to a PC with IP: {pc_ip!r}")
                                continue

                        if deploy_pc_config["num_pc_vms"] not in pc_obj.PC_VM_SIZE:
                            self.exceptions.append("Invalid number of PC VMs. Allowed values are 1(Single PC) or 3("
                                                   "Scale-out-PC)")
                            continue

                        if deploy_pc_config["pc_size"] not in pc_obj.PC_VM_SPEC:
                            self.exceptions.append(
                                f"{cluster_ip}: Wrong VM size provided. Allowed sizes are: "
                                f"{list(pc_obj.PC_VM_SPEC.keys())}")
                            continue

                        # Check if PC VMs already exists in the cluster
                        deploy_pc_config["vm_name_list"] = [
                            f"{deploy_pc_config['pc_vm_name_prefix']}-{i}" for i in
                            range(deploy_pc_config["num_pc_vms"])
                        ]
                        vm_op = VM(pe_session)
                        vm_name = next((vm["name"] for vm in vm_op.read()
                                        if vm["name"] in deploy_pc_config["vm_name_list"]), None)
                        if vm_name:
                            self.exceptions.append(
                                f"VM with name {vm_name} already exists in Cluster {cluster_info}. "
                                "Please provide a different PC VM name prefix")
                            continue

                        # Check for sufficient PC VM IPs
                        if len(deploy_pc_config["ip_list"]) < deploy_pc_config["num_pc_vms"]:
                            self.exceptions.append(
                                f"Insufficient PC IPs. Need {deploy_pc_config['num_pc_vms']} IPs for "
                                f"this deployment, given {len(deploy_pc_config['ip_list'])}")
                            continue

                        # Get Container UUID
                        container_op = Container(pe_session)
                        container_uuid = next((container["containerUuid"] for container in container_op.read() if
                                               container["name"] == deploy_pc_config['container_name']), None)
                        if not container_uuid:
                            self.exceptions.append(f"Container {deploy_pc_config['container_name']!r} doesn't exist "
                                                   f"in the cluster {cluster_info}")
                            continue
                        deploy_pc_config["container_uuid"] = container_uuid

                        # Get Network UUID
                        network_op = Network(pe_session)
                        network_uuid = next((network["uuid"] for network in network_op.read() if
                                             network["name"] == deploy_pc_config['network_name']), None)
                        if not network_uuid:
                            self.exceptions.append(f"Network {deploy_pc_config['network_name']!r} doesn't exist in "
                                                   f"the cluster {cluster_info}")
                            continue
                        deploy_pc_config["network_uuid"] = network_uuid

                        cvm_credential = cluster_details.get("cvm_credential")
                        # get credentials from the payload
                        try:
                            cluster_details["cvm_username"], cluster_details["cvm_password"] = (
                                read_creds(data=self.data, credential=cvm_credential))
                        except Exception as e:
                            self.exceptions.append(f"Failed to upload PC software. Error: {e}")
                            continue

                        try:
                            # Download & upload PC software to PE
                            upload_status, upload_error_message, deploy_pc_config = \
                                self.upload_pc_software(cluster_ip, cluster_details["cvm_username"],
                                                        cluster_details["cvm_password"], deploy_pc_config)
                        except Exception as e:
                            self.exceptions.append(f"Uploading PC software failed with the error: {e}")
                            continue

                        if upload_status:
                            # Deploy PC in PE
                            # Get PC VM spec based on the scale type & VM Size
                            self.logger.info(f"{cluster_ip}: Deploying PC VM")
                            pc_vm_spec = pc_obj.PC_VM_SPEC[deploy_pc_config["pc_size"]]
                            deploy_pc_config.update(pc_vm_spec)
                            self.logger.info(f"Deploying PC VM with the below PC config in the cluster: {cluster_info}")
                            self.logger.info(deploy_pc_config)

                            # When we are deploying multiple PC VMs on the same cluster, we can't enable CMSP on all
                            # because deployment will fail with trust error. Hence, only enabling CMSP on the first
                            # PC VM where register_to_pc is true.
                            pc_vm_config = deepcopy(deploy_pc_config)
                            if (deploy_pc_config.get("register_to_pe") is not True and
                               deploy_pc_config.get("deploy_cmsp") is True):
                                # Let's configure CMSP later
                                pc_vm_config.pop("deploy_cmsp")
                            task_uuid = pc_obj.deploy_pc_vm(pc_config=pc_vm_config)
                            if task_uuid:
                                pc_task_monitor = TaskMonitor(pe_session, task_uuid_list=[task_uuid])
                                pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 60
                                pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 5400  # 90 mins wait timeout
                                app_response, status = pc_task_monitor.monitor()

                                if app_response:
                                    self.exceptions.append(
                                        f"{cluster_info} Task have failed while deploying PC VM. {app_response}")
                                    continue

                                if not status:
                                    self.exceptions.append(f"{cluster_info} Timed out. Deployment of PC VMs didn't "
                                                           f"happen in the prescribed timeframe")
                                    continue
                                if not app_response and status:
                                    self.logger.info(f"{cluster_info} PC VM deployment successful!")

                                pc_ip = f"{deploy_pc_config.get('vip') or deploy_pc_config['ip_list'][0]}"
                                # wait for PC services to come up
                                self.logger.info(f"Waiting for PC services to come up in the PC: {pc_ip}")
                                # todo add heartbeat check
                                sleep(120)

                                # Register PC to PE
                                try:
                                    if deploy_pc_config.get("register_to_pe", False) is True:
                                        self.logger.info(f"Registering PC {pc_ip!r} to PE {cluster_info}")
                                        data = {
                                            "pc_ip": pc_ip,
                                            "vaults": self.data["vaults"],
                                            "vault_to_use": self.data["vault_to_use"],
                                            "pc_credential": deploy_pc_config.get("pc_credential")
                                        }
                                        create_pc_objects(data)
                                        register_to_pc_op = RegisterToPc(data=data)
                                        status = register_to_pc_op.register_cluster(cluster_ip, pe_session)
                                        if status:
                                            self.logger.info(f"Successfully submitted a request to register PC {pc_ip!r}"
                                                             f" to PE {cluster_info}")
                                        else:
                                            self.logger.error(f"Failed to register PC {pc_ip!r} to PE {cluster_info}")
                                except Exception as e:
                                    self.exceptions.append(f"Registering PC {pc_ip!r} to PE {cluster_info!r}"
                                                           f" failed with the error: {e}")

                                # Enable CMSP in PC
                                try:
                                    if (deploy_pc_config.get("deploy_cmsp") is True and
                                       not deploy_pc_config.get("register_to_pe")):
                                        # Use default session as creds haven't been set yet
                                        pc_session = RestAPIUtil(
                                            pc_ip,
                                            user=self.DEFAULT_USERNAME,
                                            pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                            port="9440", secured=True)
                                        cmsp_pc_obj = PrismCentral(pc_session)
                                        self.logger.info(f"Enabling CMSP in the PC {pc_ip!r}")
                                        response = cmsp_pc_obj.enable_cmsp(
                                            cmsp_subnet_mask=deploy_pc_config.get("cmsp_subnet_mask"),
                                            cmsp_internal_network=deploy_pc_config.get("cmsp_internal_network"),
                                            cmsp_default_gateway=deploy_pc_config.get("cmsp_default_gateway"),
                                            cmsp_ip_address_range=deploy_pc_config.get("cmsp_ip_address_range"),
                                            pc_domain_name=deploy_pc_config.get("prism_central_service_domain_name")
                                        )
                                        if response:
                                            self.logger.info(f"CMSP enabled for the PC {pc_ip!r}")
                                        else:
                                            self.exceptions.append(f"Enabling CMSP in {pc_ip!r} failed")
                                except Exception as e:
                                    self.exceptions.append(f"Enabling CMSP in {pc_ip!r} failed with the error: {e}")
                        else:
                            self.exceptions.append(
                                f"{cluster_info}: failed to upload PC software. Error: {upload_error_message}")
                    except Exception as e:
                        self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
                                               f"with the error: {e}")
            else:
                self.logger.warning(f"PC Configuration not provided for the cluster {cluster_ip}. Skipping...")
                return
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_ip!r} "
                                   f"with the error: {e}")

    @staticmethod
    def upload_pc_software(cvm_ip: str, cvm_username: str, cvm_password: str, pc_config: dict):
        """
        Downloads and uploads PC software to PE.

        Args:
            cvm_ip (str): The IP address of the CVM.
            cvm_username (str): The username for the CVM.
            cvm_password (str): The password for the CVM.
            pc_config (dict): A dictionary containing the PC configuration.

        Returns:
            tuple: A tuple containing the upload status, upload error message, and the updated PC configuration.
        """
        ssh_cvm = SSHCvm(cvm_ip, cvm_username, cvm_password)

        metadata_file_url = pc_config.pop("metadata_file_url", None)
        file_url = pc_config.pop("file_url", None)
        md5sum = pc_config.pop("md5sum", None)
        delete_existing_software = pc_config.pop("delete_existing_software", False)

        upload_status, upload_error_message = ssh_cvm.upload_pc_deploy_software(
            pc_config["pc_version"], metadata_file_url, file_url, md5sum=md5sum,
            delete_existing_software=delete_existing_software)
        return upload_status, upload_error_message, pc_config

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        """
        Verifies if the deployed PC is accessible.

        Args:
            cluster_ip (str): The IP address of the cluster.
            cluster_details (Dict): A dictionary containing the details of the cluster.
        """
        try:
            if not (deploy_pc_configs := cluster_details.get("pc_configs")):
                return
            self.results["clusters"][cluster_ip] = {}
            for deploy_pc_config in deploy_pc_configs:
                self.results["clusters"][cluster_ip][deploy_pc_config["pc_vm_name_prefix"]] = {}
                pc_vip = deploy_pc_config.get("pc_vip")
                if pc_vip:
                    status = "PASS" if self.check_cluster_vip_access(pc_vip) else f"Failed to access PC VIP {pc_vip}"
                    self.results["clusters"][cluster_ip][deploy_pc_config["pc_vm_name_prefix"]].update(
                        {"PC VIP Access": status})
                else:
                    self.results["clusters"][cluster_ip][deploy_pc_config["pc_vm_name_prefix"]].update(
                        {"PC VIP Access": "Not Applicable"})
        except Exception as e:
            self.logger.error(e)

    def check_cluster_vip_access(self, cluster_vip: str):
        """
        Checks if the Cluster VIP is accessible.

        Args:
            cluster_vip (str): The IP address of the Cluster VIP.

        Returns:
            boolean: Returns True if Cluster VIP is accessible else False.
        """
        default_pe_session = RestAPIUtil(cluster_vip, user=self.DEFAULT_USERNAME,
                                         pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                         port="9440", secured=True)
        try:
            cluster_obj = ClusterV2(default_pe_session)
            self.logger.info("Checking if Cluster VIP is accessible and throws unauthorized error")
            cluster_obj.read(endpoint="cluster")
        except Exception as e:
            self.logger.warning(e)
            if "401 Client Error: UNAUTHORIZED" in e.message:
                return True
            else:
                return False
