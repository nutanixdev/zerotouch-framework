from typing import Dict
from .helpers.v1.multicluster import MultiCluster
from .helpers.v2.cluster import Cluster as PeCluster
from .cluster_script import ClusterScript
from .helpers.v1.container import Container
from .helpers.v3.network import Network
from .helpers.v3.vm import VM
from .helpers.ssh_cvm import SSHCVM
from .helpers.pc_deployment_helper import PCDeploymentUtil
from .helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.log_utils import get_logger

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
        if cluster_details.get("deploy_pc_config"):
            self.logger.info(f"Executing for cluster: {cluster_ip}")
            self.results["clusters"][cluster_ip] = {}
            if self.parallel:
                self.set_current_thread_name(cluster_ip)
            pe_session = cluster_details["pe_session"]

            # get Cluster UUIDs
            if not cluster_details.get("cluster_info", {}).get("uuid"):
                cluster = PeCluster(pe_session)
                cluster.get_cluster_info()
                cluster_details["cluster_info"].update(cluster.cluster_info)

            try:
                # Check if PE is already registered to PC
                pc_ip = self.get_pe_registered_pc_ip(pe_session)
                if pc_ip:
                    self.logger.warning(f"Cluster '{cluster_ip}' is already registered to a PC with IP: '{pc_ip}'")
                    return

                if not cluster_details.get("deploy_pc_config", {}):
                    self.exceptions.add("PC Configuration not provided for PC deployment")
                    return
                deploy_pc_config = cluster_details["deploy_pc_config"]
                self.pc_vip = deploy_pc_config["pc_vip"]

                # Check if PC VMs already exists in the cluster
                deploy_pc_config["vm_name_list"] = ["{}-{}{}".format(deploy_pc_config["pc_vm_name_prefix"], node_index,
                                                                     deploy_pc_config.get("pc_vm_name_postfix", "")) for node_index in range(deploy_pc_config["num_pc_vms"])]
                cluster_vm_list = [vm["spec"]["name"] for vm in VM(pe_session).list()]
                for pc_vm_name in deploy_pc_config["vm_name_list"]:
                    if pc_vm_name in cluster_vm_list:
                        self.exceptions.append(f"VM with name {pc_vm_name} already exists in Cluster. Please provode a different PC VM prefix name")
                        return

                # Check for sufficient PC VM IPs
                if len(deploy_pc_config["ip_list"]) < deploy_pc_config["num_pc_vms"]:
                    self.exceptions.append("Insufficient PC IPs. Need {0} IP's for this deployment, given {1}".format(
                        deploy_pc_config["num_pc_vms"], deploy_pc_config["ip_list"]))
                    return

                # Get Container UUID
                container_op = Container(pe_session)
                container_uuid = next((container["containerUuid"] for container in container_op.read() if container["name"] == deploy_pc_config['container_name']), None)
                if not container_uuid:
                    self.exceptions.append(f"Container {deploy_pc_config['container_name']} not found in cluster {cluster_ip}")
                    return
                deploy_pc_config["container_uuid"] = container_uuid

                # Get Network UUID
                network = Network(session=pe_session)
                filter_criteria = f"name=={deploy_pc_config['network_name']}"
                subnets_response = network.list(filter=filter_criteria)
                if not subnets_response:
                    self.exceptions.append(f"Subnet {deploy_pc_config['network_name']} not found in cluster {cluster_ip}")
                    return
                deploy_pc_config["network_uuid"] = subnets_response[0]["metadata"]["uuid"]

                # Download & upload PC software to PE
                upload_status, upload_error_message, deploy_pc_config = \
                    self.upload_pc_software(cluster_ip, cluster_details["cvm_username"],
                                            cluster_details["cvm_password"], deploy_pc_config)

                if upload_status:
                    # Deploy PC in PE
                    # Get PC VM spec based on the scale type & VM Size
                    pc_deploy_util = PCDeploymentUtil(pe_session=pe_session)
                    pc_vm_config, error_message = pc_deploy_util.get_prism_central_vm_size_spec(pc_size=deploy_pc_config["pc_size"])
                    if not pc_vm_config:
                        self.exceptions.append(f"Failed to get PC VM spec for size {deploy_pc_config['size']}. Error: {error_message}")
                    deploy_pc_config.update(pc_vm_config)
                    self.logger.info(deploy_pc_config)
                    task_uuid = pc_deploy_util.deploy_pc_vm(pc_config=deploy_pc_config)
                    if task_uuid:
                        app_response, status = PcTaskMonitor(pe_session, task_uuid_list=[task_uuid]).monitor()

                        if app_response:
                            self.exceptions.append(f"Task have failed while deploying PC VM. {app_response}")

                        if not status:
                            self.exceptions.append(
                                "Timed out. Deployment of PC VMs didn't happen in the prescribed timeframe")
                        if not app_response and status:
                            self.results["clusters"][cluster_ip].update()
                else:
                    self.exceptions.append(f"Failed to upload PC software. Error: {upload_error_message}")
            except Exception as e:
                cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
                self.exceptions.append(f"{type(self).__name__} failed for the cluster {cluster_info} "
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
                deploy_pc_config["pc_version"], metadata_file_url, file_url, md5sum=md5sum, delete_existing_software=delete_existing_software)
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
                pc_vip = deploy_pc_config["pc_vip"]
                status = "PASS" if self.check_cluster_vip_access(pc_vip) else f"Failed to access PC VIP {pc_vip}"
                self.results["clusters"][cluster_ip].update({"PC VIP Access": status})
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
