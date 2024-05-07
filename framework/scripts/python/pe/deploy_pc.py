from typing import Dict
from framework.scripts.python.helpers.v1.multicluster import MultiCluster
from framework.scripts.python.helpers.v2.cluster import Cluster as PeCluster
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.container import Container
from framework.scripts.python.helpers.v3.network import Network
from framework.scripts.python.helpers.v3.vm import VM
from framework.scripts.python.helpers.ssh_cvm import SSHCVM
from framework.scripts.python.helpers.pc_deployment_helper import PCDeploymentUtil
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.log_utils import get_logger
from framework.helpers.helper_functions import read_creds

logger = get_logger(__name__)


class DeployPC(ClusterScript):
    """
    Class to deploy PC in PE
    """
    DEFAULT_USERNAME = "admin"
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        super(DeployPC, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        """Deploy PC in PE

        Args:
            cluster_ip (str): Cluster IP address
            cluster_details (dict): Cluster details
        """
        try:
            if deploy_pc_config := cluster_details.get("deploy_pc_config"):
                self.results["clusters"][cluster_ip] = {}
                if self.parallel:
                    self.set_current_thread_name(cluster_ip)
                self.logger.info(f"Executing for cluster: {cluster_ip!r}")
                pe_session = cluster_details["pe_session"]

                # get Cluster UUIDs
                if not cluster_details.get("cluster_info", {}).get("uuid"):
                    cluster = PeCluster(pe_session)
                    cluster.get_cluster_info()
                    cluster_details["cluster_info"].update(cluster.cluster_info)

                cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']!r}" if (
                    'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

                try:
                    if deploy_pc_config.get("check_existing_pc", True):
                        # Check if PE is already registered to PC
                        pc_ip = self.get_pe_registered_pc_ip(pe_session)
                        if pc_ip:
                            self.logger.warning(
                                f"Cluster {cluster_ip!r} is already registered to a PC with IP: {pc_ip!r}")
                            return

                    # Check if PC VMs already exists in the cluster
                    deploy_pc_config["vm_name_list"] = [
                        "{}-{}{}".format(deploy_pc_config["pc_vm_name_prefix"], node_index,
                                         deploy_pc_config.get("pc_vm_name_postfix", "")) for
                        node_index in range(deploy_pc_config["num_pc_vms"])]
                    cluster_vm_list = [vm["spec"]["name"] for vm in VM(pe_session).list()]
                    for pc_vm_name in deploy_pc_config["vm_name_list"]:
                        if pc_vm_name in cluster_vm_list:
                            self.exceptions.append(
                                f"VM with name {pc_vm_name} already exists in Cluster {cluster_info}. "
                                "Please provide a different PC VM prefix name")
                            return

                    # Check for sufficient PC VM IPs
                    if len(deploy_pc_config["ip_list"]) < deploy_pc_config["num_pc_vms"]:
                        self.exceptions.append(
                            "Insufficient PC IPs. Need {0} IP's for this deployment, given {1}".format(
                                deploy_pc_config["num_pc_vms"], deploy_pc_config["ip_list"]))
                        return

                    # Get Container UUID
                    container_op = Container(pe_session)
                    container_uuid = next((container["containerUuid"] for container in container_op.read() if
                                           container["name"] == deploy_pc_config['container_name']), None)
                    if not container_uuid:
                        self.exceptions.append(
                            f"Container {deploy_pc_config['container_name']} not found in cluster {cluster_ip}")
                        return
                    deploy_pc_config["container_uuid"] = container_uuid

                    # Get Network UUID
                    network = Network(session=pe_session)
                    filter_criteria = f"name=={deploy_pc_config['network_name']}"
                    subnets_response = network.list(filter=filter_criteria)
                    if not subnets_response:
                        self.exceptions.append(
                            f"Subnet {deploy_pc_config['network_name']} not found in cluster {cluster_ip}")
                        return
                    deploy_pc_config["network_uuid"] = subnets_response[0]["metadata"]["uuid"]

                    cvm_credential = cluster_details.pop("cvm_credential")
                    # get credentials from the payload
                    try:
                        cluster_details["cvm_username"], cluster_details["cvm_password"] = (
                            read_creds(data=self.data, credential=cvm_credential))
                    except Exception as e:
                        self.exceptions.append(e)
                        return
                    # Download & upload PC software to PE
                    upload_status, upload_error_message, deploy_pc_config = \
                        self.upload_pc_software(cluster_ip, cluster_details["cvm_username"],
                                                cluster_details["cvm_password"], deploy_pc_config)

                    if upload_status:
                        # Deploy PC in PE
                        # Get PC VM spec based on the scale type & VM Size
                        self.logger.info(f"{cluster_ip}: Deploying PC VM")
                        pc_deploy_util = PCDeploymentUtil(pe_session=pe_session)
                        if deploy_pc_config["pc_size"] not in pc_deploy_util.PC_VM_SPEC:
                            self.exceptions.append(
                                f"{cluster_ip}: Wrong VM size provided. Allowed sizes are: {pc_deploy_util.PC_VM_SPEC.keys()}")
                            return

                        pc_vm_config, error_messsage = pc_deploy_util.get_pcvm_size_spec(deploy_pc_config["pc_size"])
                        if pc_vm_config:
                            deploy_pc_config.update(pc_vm_config)
                            self.logger.info(deploy_pc_config)

                            task_uuid = pc_deploy_util.deploy_pc_vm(pc_config=deploy_pc_config)
                            if task_uuid:
                                pc_task_monitor = PcTaskMonitor(pe_session, task_uuid_list=[task_uuid])
                                pc_task_monitor.DEFAULT_CHECK_INTERVAL_IN_SEC = 60
                                pc_task_monitor.DEFAULT_TIMEOUT_IN_SEC = 3600  # 45 mins wait timeout
                                app_response, status = pc_task_monitor.monitor()

                                if app_response:
                                    self.exceptions.append(
                                        f"{cluster_info} Task have failed while deploying PC VM. {app_response}")

                                if not status:
                                    self.exceptions.append(
                                        f"{cluster_info} Timed out. Deployment of PC VMs didn't happen in the prescribed timeframe")
                                if not app_response and status:
                                    self.logger.info(f"{cluster_info} PC VM deployment successful!")
                        else:
                            self.exceptions.append(f"{cluster_info} Failed to deploy PC VMs. Error: {error_messsage}")
                    else:
                        self.exceptions.append(
                            f"{cluster_info} Failed to upload PC software. Error: {upload_error_message}")
                except Exception as e:
                    self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info!r} "
                                           f"with the error: {e}")
            else:
                self.logger.warning(f"PC Configuration not provided for the cluster {cluster_ip}")
                return
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_ip!r} "
                                   f"with the error: {e}")

    def upload_pc_software(self, cvm_ip: str, cvm_username: str, cvm_password: str, deploy_pc_config: dict):
        """Download & Upload PC software to PE

        Args:
            cvm_ip (str): CVM IP Address
            cvm_username (str): CVM username
            cvm_password (str): CVM password
            deploy_pc_config (dict): PC configuration passed to the function

        Returns:
            tuple: (upload_status, upload_error_message, updated_deploy_pc_config)
        """
        # Initialize the status & error message
        upload_status, upload_error_message = None, None

        # todo change logic. AI: @kousalya
        if deploy_pc_config.get("metadata_file_url") and deploy_pc_config.get("file_url"):
            self.logger.info("Downloading PC Software files")
            ssh_cvm = SSHCVM(cvm_ip, cvm_username, cvm_password)
            metadata_file_url = deploy_pc_config.pop("metadata_file_url")
            file_url = deploy_pc_config.pop("file_url")
            md5sum = None
            if deploy_pc_config.get("md5sum"):
                md5sum = deploy_pc_config.pop("md5sum")
            delete_existing_software = deploy_pc_config.pop("delete_existing_software")
            upload_status, upload_error_message = ssh_cvm.upload_pc_deploy_software(
                deploy_pc_config["pc_version"], metadata_file_url, file_url, md5sum=md5sum,
                delete_existing_software=delete_existing_software)
        return upload_status, upload_error_message, deploy_pc_config

    @staticmethod
    def get_pe_registered_pc_ip(pe_session):
        pc_ip = None
        cluster = MultiCluster(pe_session)
        response = cluster.get_cluster_external_state()
        if response:
            for data in response:
                if data.get('clusterDetails'):
                    pc_ip = data['clusterDetails'].get("ipAddresses", [None])[0]
        return pc_ip

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        """Verify is the deployed PC is accessible
        """
        try:
            if cluster_details.get("deploy_pc_config", {}):
                deploy_pc_config = cluster_details["deploy_pc_config"]
                pc_vip = deploy_pc_config.get("pc_vip")
                if pc_vip:
                    status = "PASS" if self.check_cluster_vip_access(pc_vip) else f"Failed to access PC VIP {pc_vip}"
                    self.results["clusters"][cluster_ip].update({"PC VIP Access": status})
                else:
                    self.results["clusters"][cluster_ip].update({"PC VIP Access": "Not Applicable"})
                self.data["json_output"] = self.results
        except Exception as e:
            self.logger.error(e)

    def check_cluster_vip_access(self, cluster_vip: str):
        """
        Check if the Cluster Vip is accessible

        Args:
            cluster_vip (str): IP Address of the Cluster VIP

        Returns:
            boolean: Returns True if Cluster VIP is accessible else False
        """
        default_pe_session = RestAPIUtil(cluster_vip, user=self.DEFAULT_USERNAME,
                                         pwd=self.DEFAULT_SYSTEM_PASSWORD,
                                         port="9440", secured=True)
        try:
            cluster_obj = PeCluster(default_pe_session)
            self.logger.info("Checking if Cluster VIP is accessible and throws unauthorized error")
            cluster_obj.read(endpoint="cluster")
        except Exception as e:
            self.logger.warning(e)
            if "401 Client Error: UNAUTHORIZED" in e.message:
                return True
            else:
                return False
