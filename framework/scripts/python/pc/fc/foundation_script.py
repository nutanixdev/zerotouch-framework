import time
import json
import logging
from copy import deepcopy
from typing import Dict, List
from framework.helpers.log_utils import get_logger
from framework.helpers.general_utils import divide_chunks, get_subnet_mask
from framework.helpers.helper_functions import create_pc_objects
from framework.scripts.python.helpers.fc.imaged_nodes import ImagedNode
from framework.scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.fc.image_cluster_script import ImageClusterScript
from framework.scripts.python.helpers.fc.monitor_fc_deployment import MonitorDeployment
from framework.scripts.python.helpers.batch_script import BatchScript
from framework.scripts.python.helpers.fc.update_fc_heartbeat_interval import UpdateFCHeartbeatInterval
from framework.scripts.python.helpers.fc.enable_one_node import EnableOneNode


logger = get_logger(__name__)


class FoundationScript(Script):
    """
    Steps:
    1. Iterate through blocks & sites
    2. Deploy site:
        1. Gather AOS & AHV URL
        2. Gather global n/w config
        3. Get node details
    """

    def __init__(self, data: Dict):
        self.data = data
        self.pod = self.data["pod"]
        self.blocks = self.pod.get("pod_blocks", {})
        self.ipam_obj = self.data.get("ipam_session")
        self.cred_details = {}
        super(FoundationScript, self).__init__()
        self.logger = self.logger or logger

    def get_ip_and_create_host_record(self, fqdn: str, subnet: str = None, ip: str = None) -> tuple:
        """Get IP and create host record in IPAM

        Args:
            fqdn (str): Fully qualified Domain Name to create host record
            subnet (str, optional): Subnet to get free IP from. Defaults to None.
            ip (str, optional): IP Address if already passed in the config file. Defaults to None.

        Returns:
            tuple (str, str): Return IP Address and error message if there is any error.
        """
        if ip:
            if self.ipam_obj.check_host_record_exists(ip):
                self.logger.warning(f"Host record present for given IP {ip}. Skipping host record creation")
            else:
                self.logger.info(f"Creating Host record {fqdn} for given IP {ip}")
                _, error = self.ipam_obj.create_host_record(fqdn=fqdn, ip=ip)
                if error:
                    return None, f"Failed to create host record: {error}"
            return ip, ""
        elif subnet:
            self.logger.info("Fetching Next available free IP from IPAM")
            ip, error = self.ipam_obj.create_host_record_with_next_available_ip(network=subnet, fqdn=fqdn)
            if error:
                return None, f"Failed to get ip from ipam: {error}"
            self.logger.info(f"Got IP {ip} from IPAM for fqdn {fqdn}")
            return ip, ""
        else:
            return None, "Niether Subnet or IP was provided to query IPAM"

    def update_node_ip_details(self, existing_node_detail_dict: Dict, cluster_node_details: List, network: Dict) -> tuple:
        """Update Node IP details

        Args:
            existing_node_detail_dict (Dict): Existing Node details
            cluster_node_details (List): Cluster node details passed in config
            network (Dict): Network details to update

        Returns:
            tuple (dict, str): Return Updated node dict & error message if there is an error
        """
        for node in cluster_node_details:
            node_info = existing_node_detail_dict[node["node_serial"]]
            hypervisor_hostname = node.get("hypervisor_hostname", node_info["hypervisor_hostname"])
            # If there is ipam_obj, fetch IPs from IPAM & Create host record
            if self.ipam_obj:
                host_ip, error = self.get_ip_and_create_host_record(
                    fqdn=f"{hypervisor_hostname}.{network['domain']}", subnet=network.get("host_subnet"),
                    ip=node.get("host_ip"))
                if error:
                    return False, f"Failed to update Host IP: {error}"
                cvm_ip, error = self.get_ip_and_create_host_record(
                    fqdn=f"{node['node_serial']}-cvm.{network['domain']}", subnet=network.get("host_subnet"),
                    ip=node.get("cvm_ip"))
                if error:
                    return False, f"Failed to update CVM IP: {error}"
                ipmi_ip, error = self.get_ip_and_create_host_record(
                    fqdn=f"{node['node_serial']}-ipmi.{network['domain']}", subnet=network.get("ipmi_subnet"),
                    ip=node.get("ipmi_ip"))
                if error:
                    self.logger.warning(f"Failed to update IPMI IP: {error}")
            else:
                host_ip = node.get("host_ip", node_info["hypervisor_ip"])
                cvm_ip = node.get("cvm_ip", node_info["cvm_ip"])
                ipmi_ip = node.get("ipmi_ip", node_info["ipmi_ip"])
            node_info["hypervisor_ip"] = host_ip
            node_info["hypervisor_gateway"] = network["host_gateway"]
            node_info["hypervisor_netmask"] = get_subnet_mask(subnet=network["host_subnet"])
            node_info["cvm_ip"] = cvm_ip
            node_info["hypervisor_hostname"] = hypervisor_hostname
            node_info["cvm_gateway"] = network["host_gateway"]
            node_info["cvm_netmask"] = get_subnet_mask(subnet=network["host_subnet"])
            node_info["ipmi_ip"] = ipmi_ip
            node_info["ipmi_gateway"] = network["ipmi_gateway"]
            node_info["ipmi_netmask"] = get_subnet_mask(subnet=network["ipmi_subnet"])
        return existing_node_detail_dict, None

    def update_cluster_info_with_site_info(self, cluster_info: Dict, site_info: Dict):
        """Update cluster info with site info

        Args:
            cluster_info (Dict): Cluster info to update
            site_info (Dict): Site info

        Returns:
            dict: Updated cluster info
        """
        cluster_info["use_existing_network_settings"] = cluster_info.get("use_existing_network_settings", site_info["use_existing_network_settings"])
        cluster_info["network"] = cluster_info.get("network", site_info.get("network"))
        cluster_info["re-image"] = cluster_info.get("re-image", site_info["re-image"])
        cluster_info["dns_servers"] = cluster_info.get("name_servers_list", site_info["name_servers_list"])
        cluster_info["ntp_servers"] = cluster_info.get("ntp_servers_list", site_info["ntp_servers_list"])
        cluster_info["imaging_parameters"] = site_info.get("imaging_parameters")
        return cluster_info

    def get_fc_deployment_payloads(self, site_info: Dict):
        """Create Foundation Central Deployment payload

        Args:
            site_info (Dict): Site information

        Returns:
            tuple (list, list): List of Single node deployment with imaging, List of FC Deployment payload (with and without imaging)
        """
        imaged_node_obj = ImagedNode(self.pc_session)
        fc_available_node_list, error = imaged_node_obj.node_details()

        if error:
            self.exceptions.append(error)
            return

        if fc_available_node_list:
            fc_deployment_payload_list = []
            single_node_imaging_deployment_payload_list = []
            for cluster_info in site_info["clusters"]:
                cluster_info = self.update_cluster_info_with_site_info(cluster_info, site_info)
                node_serial_list = [node["node_serial"] for node in cluster_info["node_details"]]

                # Get the existing node_details for the given node_serials
                existing_node_detail_dict = imaged_node_obj.node_details_by_node_serial(node_serial_list, fc_available_node_list)
                if cluster_info["cluster_size"] != len(existing_node_detail_dict):
                    self.exceptions.append(f"{cluster_info['cluster_name']}: Not enough available nodes found in Foundation Central for "
                                           f"given cluster_size: {cluster_info['cluster_size']} & node_serails: {node_serial_list}")
                else:
                    updated_node_detail_dict = {}
                    ip_error = ""
                    if not cluster_info["use_existing_network_settings"]:
                        if cluster_info["network"]:
                            updated_node_detail_dict, ip_error = self.update_node_ip_details(existing_node_detail_dict, cluster_info["node_details"],
                                                                                             cluster_info["network"])
                            if not self.ipam_obj:
                                if not cluster_info.get("cluster_vip"):
                                    self.logger.warning(f"Cluster VIP not provided. Proceeding without Cluster VIP for cluster {cluster_info['cluster_name']}")
                            else:
                                cluster_vip, cluster_vip_error = self.get_ip_and_create_host_record(
                                    fqdn=f"{cluster_info['cluster_name']}.{cluster_info['network']['domain']}", subnet=cluster_info["network"].get("host_subnet"),
                                    ip=cluster_info.get("cluster_vip"))
                                if cluster_vip_error:
                                    ip_error += cluster_vip_error
                                else:
                                    cluster_info["cluster_vip"] = cluster_vip
                        else:
                            ip_error = f"Network details not provided to assign new network settings for cluster {cluster_info['cluster_name']}"
                    else:
                        # Re-using exisiting network settings
                        updated_node_detail_dict = existing_node_detail_dict

                    if not ip_error:
                        imaged_cluster_obj = ImagedCluster(self.pc_session)
                        fc_payload, error = imaged_cluster_obj.create_fc_deployment_payload(cluster_info, updated_node_detail_dict.values())
                        if error:
                            self.exceptions.append(f"Error creating deployment payload for cluster {cluster_info['cluster_name']}: {error}")
                        if cluster_info["cluster_size"] == 1 and cluster_info["re-image"]:
                            single_node_imaging_deployment_payload_list.append(fc_payload)
                        else:
                            fc_deployment_payload_list.append(fc_payload)
                    else:
                        self.exceptions.append(ip_error)
            self.logger.debug(f"single_node_imaging_deployment_payload_list: {single_node_imaging_deployment_payload_list}")
            self.logger.debug(f"fc_deployment_payload_list: {fc_deployment_payload_list}")
            return single_node_imaging_deployment_payload_list, fc_deployment_payload_list
        else:
            self.exceptions.append("There are no nodes discovered in FC. Please check if FC is enabled/nodes are been discovered")

    def get_imaging_node_deployment_list(self, single_node_imaging_deployment_payload_list: List, fc_deployment_payload_list: List, site_config: Dict):
        """Get imaging only FC deployment payload lists & deploy only cluster deployment payload lists for the imaging nodes

        Args:
            single_node_imaging_deployment_payload_list (List): List of the single node deployment that needs to be imaged
            fc_deployment_payload_list (List): List of FC deployment lists with or without imaging
            site_config (Dict): Site configuration

        Returns:
            tuple: (
                    imaging_only_deployment_list: Image only FC Deployment lists,
                    single_node_imaging_deployment_payload_list: Updated single node deployment list without imaging,
                    fc_deployment_payload_list: Updated FC deployment list with or without imaging
                    )
        """
        image_node_list = []
        if len(single_node_imaging_deployment_payload_list) > 1:
            for deployment in single_node_imaging_deployment_payload_list:
                for node in deployment["nodes_list"]:
                    node_data = deepcopy(node)
                    image_node_list.append(node_data)
                    node["image_now"] = False

        elif len(single_node_imaging_deployment_payload_list) == 1:
            image_node_list.append(single_node_imaging_deployment_payload_list[0]["nodes_list"][0])
            # Get an imaging deployment to combine with single node imaging deployment payload
            for fc_deployment in fc_deployment_payload_list:
                if fc_deployment["nodes_list"][0]["image_now"]:
                    for node in fc_deployment["nodes_list"]:
                        node_data = deepcopy(node)
                        image_node_list.append(node_data)
                        node["image_now"] = False
                    single_node_imaging_deployment_payload_list.append(fc_deployment)
                    fc_deployment_payload_list.remove(fc_deployment)
                    break
        if len(image_node_list) < 1:
            self.exceptions.append("No nodes to image")
            return None, None, None
        elif len(image_node_list) == 1:
            self.exceptions.append("Cannot image a single one node using FC.")
            return None, None, None
        else:
            # Divide into chuck of 'nodes_per_imaging_deployment'
            nodes_per_imaging_deployment = self.data.get("nodes_per_imaging_deployment") if self.data.get("nodes_per_imaging_deployment") else 3
            image_nodes_list = [i for i in divide_chunks(image_node_list, nodes_per_imaging_deployment)]
            if len(image_nodes_list[-1]) == 1:
                # if nodes_per_imaging_deployment is 2, add the extra node to another deployment
                if nodes_per_imaging_deployment == 2:
                    extra_node = image_nodes_list[-1]
                    image_nodes_list[-2].extend(extra_node)
                    image_nodes_list.pop(-1)
                else:
                    # if nodes_per_imaging_deployment is not 2, add the borrow a node from another deployment
                    borrow_node = image_nodes_list[-2].pop(-1)
                    image_nodes_list[-1].append(borrow_node)

            imaging_only_deployment_list = []
            index = 1
            imaged_cluster_obj = ImagedCluster(self.pc_session)
            for nodes_list in image_nodes_list:
                image_node_spec = imaged_cluster_obj._get_default_spec()
                image_node_spec["cluster_name"] = "imaging_nodes_set_{0}".format(index)
                image_node_spec["nodes_list"] = list(nodes_list)
                image_node_spec["skip_cluster_creation"] = True
                image_node_spec.update(imaged_cluster_obj.get_aos_ahv_spec(site_config["imaging_parameters"]))
                image_node_spec["common_network_settings"] = {
                        "cvm_dns_servers": site_config["name_servers_list"],
                        "hypervisor_dns_servers": site_config["name_servers_list"],
                        "cvm_ntp_servers": site_config["ntp_servers_list"],
                        "hypervisor_ntp_servers": site_config["ntp_servers_list"],
                    }
                imaging_only_deployment_list.append(image_node_spec)
                index += 1
            return imaging_only_deployment_list, single_node_imaging_deployment_payload_list, fc_deployment_payload_list

    def get_post_imaging_batch_scripts(self, deployments_to_run: List, fc_deployment_logger: logging.getLogger):
        """Get batch sripts to run post imaging scripts & FC deployment scripts

        Args:
            deployments_to_run (List): FC Deployment list post imaging
            fc_deployment_logger (logging.getLogger): Logger handler to use for logging

        Returns:
            tuple: Batchscripts for post imaging & FC deployment to run
        """
        post_imaging_scripts_op = BatchScript()
        post_imaging_deployment_op = BatchScript()
        update_fc_heartbeat_interval_op = BatchScript(parallel=True, max_workers=10)
        if self.data.get("test_enable_one_node"):
            enable_one_node_op = BatchScript(parallel=True, max_workers=10)
        for image_node_deployment in deployments_to_run:
            for node in image_node_deployment["nodes_list"]:
                update_fc_heartbeat_interval_op.add(UpdateFCHeartbeatInterval(node["cvm_ip"], self.cvm_username, self.cvm_password,
                                                                              interval_min=1, fc_deployment_logger=fc_deployment_logger))
                if self.data.get("test_enable_one_node"):
                    enable_one_node_op.add(EnableOneNode(node["cvm_ip"], self.cvm_username, self.cvm_password, fc_deployment_logger=fc_deployment_logger))
            post_imaging_deployment_op.add(ImageClusterScript(pc_session=self.pc_session, cluster_data=image_node_deployment,
                                                          fc_deployment_logger=fc_deployment_logger))
        post_imaging_scripts_op.add(update_fc_heartbeat_interval_op)
        if self.data.get("test_enable_one_node"):
            post_imaging_scripts_op.add(enable_one_node_op)
        return post_imaging_scripts_op, post_imaging_deployment_op

    def get_deployment_batch_scripts(self, fc_deployment_payload_list: List, fc_deployment_logger: logging.getLogger) -> BatchScript:
        """Create batch scripts for FC Deployments

        Args:
            fc_deployment_payload_list (List): List of FC deployment payloads
            fc_deployment_logger (str): Log handler to use for logging

        Returns:
            BatchScript: Batch script to run
        """
        fc_deployment_op = BatchScript(parallel=True, max_workers=10)
        for deployment in fc_deployment_payload_list:
            fc_deployment_op.add(ImageClusterScript(pc_session=self.pc_session, cluster_data=deployment, fc_deployment_logger=fc_deployment_logger))
        return fc_deployment_op

    def get_imaged_node_deployments_to_run(self, deployment_result: Dict, imaging_deployment_payload_list: List):
        """Get the deployments to run after imaging the nodes. Remove the deloyments for failed imaging
           Remove the deloyments for failed imaging

        Args:
            deployment_result (Dict): Result of FC deployments
            imaging_deployment_payload_list (List): FC Deployment list post imaging which needs to be updated

        Returns:
            List: List of deployments to run after imaging for successfully imaged nodes
        """
        failed_nodes_list = []
        imaging = ImagedCluster(self.pc_session)
        # Get the failed node_serial from the imaged cluster uuids
        for cluster_name, result in deployment_result.items():
            if 'imaging' in cluster_name:
                if result["result"] != "COMPLETED":
                    deployment_details = imaging.read(result["imaged_cluster_uuid"])
                    failed_nodes_list.extend([node["node_serial"] for node in deployment_details["discovered_node_details"]])

        # Get only the deployments to run for which the nodes imaging were successfully completed
        deployments_to_run = []
        for payload in imaging_deployment_payload_list:
            remove_deployment = False
            for node in payload["nodes_list"]:
                if node["node_serial"] in failed_nodes_list:
                    remove_deployment = True
            if not remove_deployment:
                deployments_to_run.append(payload)
            else:
                self.logger.warning(f"Removing deployment of cluster {payload['cluster_name']} as imaging failed for its nodes")
                self.exceptions.append(f"Deployment of cluster {payload['cluster_name']} skipped as imaging failed for its nodes")
        return deployments_to_run

    def run_fc_deployments(self, single_node_imaging_deployment_payload_list: List, fc_deployment_payload_list: List, site_config: Dict, block_info: Dict):
        """Run Foundation Central imaging and cluster deployments

        Args:
            single_node_imaging_deployment_payload_list (List): List of single node clusters with imaging
            fc_deployment_payload_list (List): List of nodes to be deployed with or without imaging
            site_config (Dict): Site configuration
            block_info (str): Block Configuration
        """
        results = {}
        block_name = block_info["pod_block_name"]
        imaging_only_deployment_list, imaging_uuid_dict, imaged_cluster_uuid_dict = [], [], []
        imaging_log_file = f"{block_name}_{site_config['site_name']}_node_imaging.log"
        deployment_log_file = f"{block_name}_{site_config['site_name']}_deployment.log"
        fc_deployment_logger = get_logger(deployment_log_file, file_name=deployment_log_file)
        fc_imaging_logger = get_logger(imaging_log_file, file_name=imaging_log_file)

        # If there are any single nodes to be imaged, create a separate imaging payload with chunk of nodes into multiple deployments
        if single_node_imaging_deployment_payload_list:
            imaging_only_deployment_list, imaging_deployment_payload_list, fc_deployment_payload_list = \
                self.get_imaging_node_deployment_list(single_node_imaging_deployment_payload_list, fc_deployment_payload_list, site_config)

        if imaging_only_deployment_list:
            # Get CVM Credentials for post imaging operations
            cvm_user = block_info.get("cvm_credential")
            self.cvm_username, self.cvm_password = self.cred_details.get(cvm_user, {}).get('username'), self.cred_details.get(cvm_user, {}).get('password')
            if not self.cvm_username and not self.cvm_password:
                self.exceptions.append("CVM Credentials are not provided")
            else:
                # Get batch script to run image only deployments
                imaging_deployment_op = self.get_deployment_batch_scripts(imaging_only_deployment_list, fc_imaging_logger)
                # Run the image only deployment(s)
                imaging_uuid_dict = imaging_deployment_op.run()

        if fc_deployment_payload_list:
            # Get batch script to run cluster deployments with or without imaging
            deployment_op = self.get_deployment_batch_scripts(fc_deployment_payload_list, fc_deployment_logger)
            # Run the deployments
            imaged_cluster_uuid_dict = deployment_op.run()

        # Creating Batch script to monitor all the FC deployments
        monitor_deployment_script = BatchScript(parallel=True, max_workers=40)

        # Start FC deployment monitoring
        if imaging_uuid_dict:
            for cluster_name, imaged_cluster_uuid in imaging_uuid_dict.items():
                monitor_deployment_script.add(MonitorDeployment(pc_session=self.pc_session, cluster_name=cluster_name,
                                                                imaged_cluster_uuid=imaged_cluster_uuid, fc_deployment_logger=fc_imaging_logger))
        if imaged_cluster_uuid_dict:
            for cluster_name, imaged_cluster_uuid in imaged_cluster_uuid_dict.items():
                monitor_deployment_script.add(MonitorDeployment(pc_session=self.pc_session, cluster_name=cluster_name,
                                                                imaged_cluster_uuid=imaged_cluster_uuid, fc_deployment_logger=fc_deployment_logger))
        if imaging_uuid_dict or imaged_cluster_uuid_dict:
            self.logger.info(f"Wait for 15 minutes to monitor deployment status for Block {block_name} Site {site_config['site_name']}")
            time.sleep(15 * 60)
            deployment_result = monitor_deployment_script.run()
            results.update(deployment_result)

        # Start executing post imaging actions to update interval times in cvms
        if imaging_uuid_dict:
            # check the nodes which are re-imaged
            deployments_to_run = self.get_imaged_node_deployments_to_run(deployment_result, imaging_deployment_payload_list)
            if deployments_to_run:
                post_imaging_scripts_op, post_imaging_deployment_op = self.get_post_imaging_batch_scripts(deployments_to_run, fc_deployment_logger)
                post_imaging_scripts_op.run()
                self.logger.info("Sleep 5 mins for the nodes to be discovered")
                time.sleep(5 * 60)
                post_imaging_uuid_dict = post_imaging_deployment_op.run()
                self.logger.info(f"Wait for 15 minutes to monitor deployment status for Block {block_name} Site {site_config['site_name']}")
                time.sleep(15 * 60)
                if post_imaging_uuid_dict:
                    monitor_deployment_script = BatchScript(parallel=True, max_workers=40)
                    for cluster_name, imaged_cluster_uuid in post_imaging_uuid_dict.items():
                        monitor_deployment_script.add(MonitorDeployment(pc_session=self.pc_session, cluster_name=cluster_name,
                                                                        imaged_cluster_uuid=imaged_cluster_uuid, fc_deployment_logger=fc_imaging_logger))
                    post_imaging_deployment_result = monitor_deployment_script.run()
                    results.update(post_imaging_deployment_result)
            else:
                self.logger.info("No cluster deployments to run after imaging, as imaging failed for the nodes.")
        return results

    def deploy_site(self, block_info: str, site_config: Dict):
        """Deploy clusters in block-sites

        Args:
            block_name (str): Name of pod-block
            site_config (dict): Site configuration
        """
        site_name = site_config["site_name"]
        self.logger.info(f"Start deployment for site {site_name}")
        # Get Foundation Central Deployment Payloads
        single_node_imaging_deployment_payload_list, fc_deployment_payload_list = self.get_fc_deployment_payloads(site_config)

        # Run Foundation Central Deployments for each site
        results = self.run_fc_deployments(single_node_imaging_deployment_payload_list, fc_deployment_payload_list, site_config, block_info)
        self.logger.info(json.dumps(results, indent=2))
        return results

    def execute(self, **kwargs):
        """Run Image cluster nodes for multiple sites
        """
        overall_result = {}
        # Looping through blocks
        for block_info in self.blocks:
            create_pc_objects(block_info, global_data=self.data)
            self.cred_details = self.data['vaults'][self.data['vault_to_use']]['credentials']
            try:
                self.logger.info(f"Start deployment for block {block_info['pod_block_name']}")
                self.pc_session = block_info["pc_session"]

                # Looping through sites
                for site_config in block_info["edge-sites"]:
                    results = self.deploy_site(block_info, site_config)
                    overall_result.update(results)
            except Exception as e:
                self.exceptions.append(e)
        self.logger.info(json.dumps(overall_result, indent=2))
        self.data["json_output"] = overall_result

    def verify(self):
        pass
