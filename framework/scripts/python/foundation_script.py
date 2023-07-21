import socket
import struct
import datetime
import time
import json
from copy import deepcopy
from helpers.log_utils import get_logger
from helpers.general_utils import divide_chunks
from helpers.rest_utils import RestAPIUtil
from helpers.helper_functions import get_aos_url_mapping, get_hypervisor_url_mapping
from scripts.python.helpers.fc.imaged_nodes import ImagedNode
from scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from scripts.python.script import Script
from scripts.python.helpers.fc.image_cluster_script import ImageClusterScript
from scripts.python.helpers.fc.monitor_fc_deployment import MonitorDeployment
from scripts.python.helpers.batch_script import BatchScript
from scripts.python.helpers.fc.update_fc_heartbeat_interval import UpdateFCHeartbeatInterval
from scripts.python.helpers.fc.enable_one_node import EnableOneNode


logger = get_logger(__name__)


class FoundationScript(Script):

    def __init__(self, data: dict):
        self.data = data
        self.mgmt_static_ips = {}
        self.ipmi_static_ips = {}
        super(FoundationScript, self).__init__()
        self.logger = self.logger or logger

    def ip_dict(self, total_cluster_size: int, ip_range: list, ip_category: str, cluster_name: str = ""):
        """Returns list of IP Dictionaries within the given IP range

        Args:
            total_cluster_size (int): Cluster size
            ip_range (str): ip range to separated by -
            ip_category (str): IP category: management or ipmi

        Returns:
            dict: Dictionary of IPs within the given IP range
        """
        ip_dict = {}
        if ip_range:
            start = struct.unpack('>I', socket.inet_aton(ip_range[0]))[0]
            end = struct.unpack('>I', socket.inet_aton(ip_range[-1]))[0]
            ip_list = [socket.inet_ntoa(struct.pack('>I', i)) for i in range(start, end+1)]
            error = self.validate_ip(total_cluster_size, len(ip_list), ip_category, cluster_name)
            if error:
                return None, error
            ip_dict = {ip: True for ip in ip_list}
        return ip_dict, ""

    def validate_ip(self, total_cluster_size: int, num_ips: int, ip_category: str, cluster_name: str):
        """Validate the given IPs with number of IPs required

        Args:
            num_ips (int): number of IPs in ip range
            ip_category (str): IP category: management or ipmi
        """
        if ip_category == "management":
            required_ips = total_cluster_size * 2
        elif ip_category == "ipmi":
            required_ips = total_cluster_size
        if num_ips < required_ips:
            error = "Insufficient {0} IPs for imaging cluster(s) {1}. Required IPs: {2}. Provided IPs: {3}.\n".format(
                ip_category, cluster_name, required_ips, num_ips)
            return error

    def get_free_ip(self, ip_dict: dict, common_ip_dict: dict = None):
        """get free ip from ip_dict based on availability

        Args:
            ip_dict (list): list of IP Dictionaries
            common_ip_dict (dict): Site level ip mapping for management/ipmi to be updated

        Returns:
            str: Free IP
        """
        for ip, available in ip_dict.items():
            if available:
                ip_dict[ip] = False
                if common_ip_dict:
                    common_ip_dict[ip] = False
                return ip
        else:
            self.logger.error("No Free IP available")
            return None

    def validate_redundancy_factor(self, cluster_size: int, redundancy_factor: int):
        """Validate the redundancy factor for a given cluster based on cluster size and redundancy factor

        Args:
            cluster_size (int): Cluster size
            redundancy_factor (int): Redundancy factor
        """
        if redundancy_factor not in [2, 3]:
            self.exceptions.append('Invalid redundancy factor {}. Nutanix supports redundancy factor 2, and also redundancy factor 3 only if the cluster has 5+ nodes'.format(redundancy_factor))
        elif redundancy_factor == 3 and cluster_size < 5:
            self.exceptions.append('With redundancy factor {0}, cluster size must be 5 or more and you selected {1} which is not compatible!'.format(redundancy_factor, cluster_size))

    def get_cluster_ip_mappings(self, cluster_info: dict, cluster_name: str):
        """Populate static ip dictionary with the provided ip range for each cluster or site

        Args:
            cluster_info (dict): Cluster information provided
            cluster_name (str): Name of the cluster

        Returns:
            (dict, dict): Management & IPMI static ip dictionary
        """
        if cluster_info.get("network", None):
            cluster_mgmt_ips, mgmt_ip_error = self.ip_dict(cluster_info["cluster_size"], cluster_info["network"]["mgmt_static_ips"],
                                                           ip_category="management", cluster_name=cluster_name)
            ipmi_static_ips, ipmi_ip_error = self.ip_dict(cluster_info["cluster_size"], cluster_info["network"]["ipmi_static_ips"],
                                                          ip_category="ipmi", cluster_name=cluster_name)
            if mgmt_ip_error or ipmi_ip_error:
                error = mgmt_ip_error+ipmi_ip_error
                return None, None, error
        else:
            cluster_mgmt_ips = self.mgmt_static_ips
            ipmi_static_ips = self.ipmi_static_ips
        return cluster_mgmt_ips, ipmi_static_ips, None

    def get_nodes_from_blockserial(self, block_serial_nodes: list, cluster_size: int):
        """Get node details based on block_serials

        Args:
            block_serials (list): list of block_serials
            cluster_size (int): Cluster size

        Returns:
            (list, str): (List of node details, Error Message)
        """
        node_details = []
        for node in block_serial_nodes:
            if node["available"] and node["imaged_node_uuid"] not in self.assigned_nodes:
                if cluster_size > 2:
                    node_details.append(node)
                    self.assigned_nodes.append(node["imaged_node_uuid"])
                elif cluster_size == 1 and node["hardware_attributes"].get("one_node_cluster"):
                    node_details.append(node)
                    self.assigned_nodes.append(node["imaged_node_uuid"])
                elif cluster_size == 2 and node["hardware_attributes"].get("two_node_cluster"):
                    node_details.append(node)
                    self.assigned_nodes.append(node["imaged_node_uuid"])
                if len(node_details) == cluster_size:
                    self.logger.info("Got {} available node details".format(len(node_details)))
                    self.logger.debug("Node details: {}".format(node_details))
                    return node_details, None
        else:
            return None, "Not enough available nodes found in block serials."

    def update_node_details(self, node_list: list, cluster_name: str, cluster_info: dict):
        """Update the node details with provided site details

        Args:
            node_list (list): List of node details with updated params
        """
        updated_node_list = []
        for node in node_list:
            if not cluster_info.get("use_existing_network_settings", self.site_data["use_existing_network_settings"]):
                network = cluster_info["network"] if cluster_info.get("network", None) else self.site_data["network"]
                mgmt_netmask, mgmt_gateway, ipmi_netmask, ipmi_gateway = self.get_netmask_gateway(network, node)
                node_spec = {
                    "hypervisor_ip": self.get_free_ip(cluster_info["cluster_mgmt_ips"], self.mgmt_static_ips),
                    "hypervisor_netmask": mgmt_netmask,
                    "hypervisor_gateway": mgmt_gateway,
                    "cvm_ip": self.get_free_ip(cluster_info["cluster_mgmt_ips"], self.mgmt_static_ips),
                    "cvm_netmask": mgmt_netmask,
                    "cvm_gateway": mgmt_gateway,
                    "ipmi_netmask": ipmi_netmask,
                    "rdma_passthrough": cluster_info.get("rdma_passthrough", False),
                    "hypervisor_type": self.site_data["imaging_parameters"]["hypervisor_type"],
                    "image_now": cluster_info.get("re-image", self.site_data.get("re-image", False)),
                    "ipmi_ip": self.get_free_ip(cluster_info["ipmi_static_ips"], self.ipmi_static_ips) if cluster_info["ipmi_static_ips"] else node["ipmi_ip"],
                    "cvm_ram_gb": cluster_info.get("cvm_ram", 12),
                    "use_existing_network_settings": False,
                    "ipmi_gateway": ipmi_gateway,
                }
                if cluster_info.get("cvm_vlan_id"):
                    node_spec["cvm_vlan_id"] = cluster_info["cvm_vlan_id"]
            elif cluster_info.get("use_existing_network_settings", self.site_data["use_existing_network_settings"]):
                node_spec = {
                    "use_existing_network_settings": True,
                    "imaged_node_uuid": node["imaged_node_uuid"],
                    "image_now": cluster_info.get("re-image", self.site_data.get("re-image", False)),
                    }
            node.update(node_spec)
            updated_node_list.append(node)
        return updated_node_list

    def update_aos_ahv_spec(self):
        """Update hypervisor iso details
        """
        return {
            "aos_package_url": self.site_data["aos_url"],
            "hypervisor_iso_details": {
                "hypervisor_type": self.site_data["imaging_parameters"]["hypervisor_type"],
                "url": self.site_data["hypervisor_url"]
            }
        }

    def update_common_network_settings(self):
        """ Update common network settings
        """
        return {
            "cvm_dns_servers": self.site_data["global_network"]["dns_servers"],
            "hypervisor_dns_servers": self.site_data["global_network"]["dns_servers"],
            "cvm_ntp_servers": self.site_data["global_network"]["ntp_servers"],
            "hypervisor_ntp_servers": self.site_data["global_network"]["ntp_servers"],
        }

    def get_node_detail_by_node_serial(self, node_serial_list: list, cluster_size: int):
        """Fetch Node details based on node serial list

        Args:
            node_serial_list (list): List of node serials
            cluster_size (int): Cluster size

        Returns:
            (list, str): (List of node details, Error Message)
        """
        node_details = []
        for node in self.node_list:
            if node["node_serial"] in node_serial_list and node["imaged_node_uuid"] not in self.assigned_nodes:
                node_details.append(node)
                self.assigned_nodes.append(node["imaged_node_uuid"])
            if cluster_size == len(node_details):
                return node_details, None
        else:
            # todo: Improve error logging, by checking if this node is assigned to different cluster or not discovered in FC
            return None, "Not enough available nodes found in Foundation Central for given node_serails: {0}".format(node_serial_list)

    def get_cluster_data(self, cluster_name: str, cluster_info: dict, block_node_list: list = None):
        """Create Cluster data for each cluster

        Args:
            cluster_name (list): Cluster name
            cluster_info (dict): Cluster info provided in json
            block_node_list (list): List of nodes details in given block serials

        Returns:
            (list, str): (List of node details, Error Message)
        """
        cluster_data = {
            "cluster_external_ip": cluster_info["cluster_vip"],
            "redundancy_factor": cluster_info["redundancy_factor"],
            "cluster_name": cluster_name,
            "cluster_size": cluster_info["cluster_size"]
        }
        if cluster_info.get("node_serials", None):
            if cluster_info["cluster_size"] > len(cluster_info["node_serials"]):
                error = "Insufficient node serials {0} for cluster {1} size {2}".format(cluster_info["node_serials"], cluster_name, cluster_info["cluster_size"])
            else:
                node_list, error = self.get_node_detail_by_node_serial(cluster_info["node_serials"], cluster_info["cluster_size"])
        else:
            node_list, error = self.get_nodes_from_blockserial(block_node_list, cluster_info["cluster_size"])
        if error:
            return None, error
        if node_list:
            cluster_data["nodes_list"] = self.update_node_details(node_list, cluster_name, cluster_info)
            if cluster_info.get("re-image", self.site_data["re-image"]):
                cluster_data.update(self.update_aos_ahv_spec())
            return cluster_data, None

    def get_site_cluster_data(self):
        """
        Generate cluster data for all the clusters in the site

        Returns:
            (list): List of cluster datas for the given site
        """
        cluster_data_list = []
        total_cluster_size = 0
        self.node_list, error = self.image_node.node_details()

        # Dictionaries to store cluster with and without node details separately
        node_serial_cluster_data = {}
        block_serial_cluster_data = {}

        if error:
            self.exceptions.append(error)
            return None, None
        if self.node_list:
            re_image_cluster = []
            for cluster_info in self.site_data["clusters"]:
                cluster_name = cluster_info["cluster_name"]
                if cluster_info.get("node_serials", None):
                    node_serial_cluster_data[cluster_name] = cluster_info
                else:
                    block_serial_cluster_data[cluster_name] = cluster_info
                if not cluster_info.get("network"):
                    # Calculating total cluster size to check sufficient management & ipmi IPs
                    total_cluster_size += cluster_info["cluster_size"]
                # Get list of nodes to re-image
                if cluster_info.get("re-image", self.site_data["re-image"]):
                    re_image_cluster.append(cluster_name)
            common_network_settings = self.update_common_network_settings()

            # Adding node_serail & block_serial cluster data to ordered dict, the cluster with node serial will be added first for cluster deployment
            site_cluster_info = {}
            site_cluster_info.update(node_serial_cluster_data)

            # Get the static ip list for site static ip list
            static_ip_error = None
            if not self.site_data["use_existing_network_settings"]:
                self.mgmt_static_ips, mgmt_ip_error = self.ip_dict(total_cluster_size, self.site_data["network"]["mgmt_static_ips"], ip_category="management")
                self.ipmi_static_ips, ipmi_ip_error = self.ip_dict(total_cluster_size, self.site_data["network"]["ipmi_static_ips"], ip_category="ipmi")
                if mgmt_ip_error or ipmi_ip_error:
                    static_ip_error = mgmt_ip_error+ipmi_ip_error
                    self.exceptions.append("Skipping Cluster deployment which shares site level network. Reason: {}".format(static_ip_error))
            # Exclusing cluster deployment which share site level netowrk for deployment if there is static ip error
            if not static_ip_error:
                site_cluster_info.update(block_serial_cluster_data)

            # todo: order block_serial_cluster_data based on cluster size
            # block_serial_cluster_data = sorted(block_serial_cluster_data.items(), key=lambda x: x[1]['cluster_size'], reverse=False)

            # Get the nodes based on block serials provided
            node_list, error = self.image_node.node_details_by_block_serial(self.site_data["node_block_serials"])
            if error:
                self.exceptions.append(error)
            sorted_imaged_nodes = []
            if node_list:
                sorted_imaged_nodes = sorted(node_list, key=lambda i: (i['block_serial'], i['node_position']))
            # Gathering data for clusters with node serials
            for cluster_name, cluster_info in site_cluster_info.items():
                cluster_mgmt_ips, ipmi_static_ips, error = self.get_cluster_ip_mappings(cluster_info, cluster_name)
                if not error:
                    cluster_info["cluster_mgmt_ips"] = cluster_mgmt_ips
                    cluster_info["ipmi_static_ips"] = ipmi_static_ips
                    cluster_data, error = self.get_cluster_data(cluster_name, cluster_info, sorted_imaged_nodes)
                    if error:
                        self.exceptions.append(error)
                    else:
                        cluster_data["common_network_settings"] = common_network_settings
                        cluster_data_list.append(cluster_data)
                else:
                    self.exceptions.append(error)

            # group the single-node clusters for re-imaging
            re_image_node_details = []
            if re_image_cluster:
                for cluster_data in cluster_data_list:
                    if cluster_data["cluster_name"] in re_image_cluster:
                        re_image_node_details.append(cluster_data)
                if len(re_image_node_details) == 1 and len(re_image_node_details[0]["nodes_list"]) == 1:
                    message = "Single node imaging is not supported in FC. Could not re-image node {0}".format(re_image_node_details[0]["nodes_list"][0]["node_serial"])
                    self.logger.warning(message)
                    self.exceptions.append(message)
                    cluster_data_list.remove(re_image_node_details[0])
                    return None, cluster_data_list
                else:
                    nodes_list = []
                    for cluster_data in re_image_node_details:
                        for node in cluster_data["nodes_list"]:
                            node_data = deepcopy(node)
                            node_data["image_now"] = True
                            nodes_list.append(node_data)
                            node["image_now"] = False
                    imgae_node_spec_list = []
                    image_nodes = divide_chunks(nodes_list, 3)
                    image_nodes_list = [i for i in image_nodes]
                    if len(image_nodes_list[-1]) == 1:
                        image_nodes_list[-2] += image_nodes_list[-1]
                        image_nodes_list.pop(-1)
                    for nodes in image_nodes_list:
                        imgae_node_spec = ImagedCluster(self.pc_session)._get_default_spec()
                        imgae_node_spec["nodes_list"] = list(nodes)
                        imgae_node_spec["skip_cluster_creation"] = True
                        imgae_node_spec.update(self.update_aos_ahv_spec())
                        imgae_node_spec["common_network_settings"] = common_network_settings
                        imgae_node_spec_list.append(imgae_node_spec)
                    return imgae_node_spec_list, cluster_data_list
            else:
                self.logger.info("There are no nodes to image.")
                return None, cluster_data_list

    def monitor_fc_deployment(self, imaged_cluster_uuid_dict: dict, fc_deployment_logger=None):
        """Monitor FC deployment(s)

        Args:
            imaged_cluster_uuid_dict (dict): Dict of cluster deployment & its imaged cluster uuid

        Returns:
            dict: Result dict with total, passed, failed and in-progress count
        """
        monitor_deployment_script = BatchScript(parallel=True, max_workers=40)
        for cluster_name, imaged_cluster_uuid in imaged_cluster_uuid_dict.items():
            monitor_deployment_script.add(MonitorDeployment(pc_session=self.pc_session, cluster_name=cluster_name,
                                                            imaged_cluster_uuid=imaged_cluster_uuid, fc_deployment_logger=fc_deployment_logger))
        deployment_result = monitor_deployment_script.run()
        self.logger.debug(f"Deployment results: {deployment_result}")
        failed_count = 0
        passed_count = 0
        inprogress_count = 0
        total_deployments = len(deployment_result)
        result = {"total_deployments": total_deployments, "passed_count": passed_count,
                  "failed_count": failed_count, "in-progess": inprogress_count}
        for cluster_name, deplotment_status in deployment_result.items():
            if deplotment_status["result"] == "FAILED":
                result["failed_count"] += 1
            elif deplotment_status["result"] == "COMPLETED":
                result["passed_count"] += 1
            elif deplotment_status["result"] == "PENDING":
                result["in-progess"] += 1
        return result

    def start_fc_deployment(self, fc_deployment_list: list, fc_deployment_logger=None):
        """
        Start FC Deployment(s)

        Args:
            fc_deployment_list (list): List of cluster data for FC deployment

        Returns:
            list: Dict of cluster deployment & its imaged cluster uuid
        """
        image_cluster_script = BatchScript(parallel=True, max_workers=10)
        for deployment_data in fc_deployment_list:
            image_cluster_script.add(ImageClusterScript(pc_session=self.pc_session, cluster_data=deployment_data, fc_deployment_logger=fc_deployment_logger))
        imaged_cluster_uuid_list = image_cluster_script.run()
        self.logger.info(f"imaged_cluster_uuid_list is {imaged_cluster_uuid_list}")
        return imaged_cluster_uuid_list

    def fc_deployment(self, fc_deployment_list: list, block_name: str, site_name: str, fc_deployment_logger=None):
        """Trigger Foundation Central deployment and monitor the deployments

        Args:
            fc_deployment_list (list): Deployment details for each cluster
            block_name (str): Name of the block
            site_name (str): Name of the site for the deployments
            log_file (str, optional): Name of the file to log the deployments logs. Defaults to None.

        Returns:
            dict: Result of site level deployments
        """
        # Start FC deployment(s)
        self.logger.info("Starting FC Deployment(s)...")
        logger.debug(f"fc_deployment: {fc_deployment_logger}")
        imaged_cluster_uuid_list = self.start_fc_deployment(fc_deployment_list, fc_deployment_logger)
        # Moitor FC deployment(s)
        self.logger.info("Monitoring FC Deploment(s)...")
        self.logger.info(imaged_cluster_uuid_list)
        if imaged_cluster_uuid_list:
            self.logger.info(f"Wait for 15 minutes to monitor deployment status for Block {block_name} Site {site_name}")
            time.sleep(15 * 60)
            result = self.monitor_fc_deployment(imaged_cluster_uuid_list, fc_deployment_logger)
            return result, None
        else:
            self.logger.warning("No imaged cluster uuid to monitor progress")
            return None, "No imaged cluster uuid to monitor progress. Check logs for error."

    def update_heartbeat_interval(self, imaging_node_list: list, interval_min: int = 1, fc_deployment_logger=None):
        """Updation the heartbeat interval in Foundation central seetings

        Args:
            imaging_node_list (list): List of node details to be imaged
            interval_min (int, optional): Interval between the hearbeat chesks in Foundation Central. Defaults to 1.
            fc_deployment_logger (Object): Logger object to be used to log the output
        """
        self.logger.info(f"Updating heartbeat interval to {interval_min} minute(s)...")
        update_fc_hearbeat_interval = BatchScript(parallel=True, max_workers=10)
        for deployment_data in imaging_node_list:
            for node in deployment_data["nodes_list"]:
                update_fc_hearbeat_interval.add(UpdateFCHeartbeatInterval(node["cvm_ip"], "nutanix", "nutanix/4u",
                                                                          interval_min, fc_deployment_logger=fc_deployment_logger))
        result = update_fc_hearbeat_interval.run()
        self.logger.debug(result)
        self.logger.info(f"Updated heartbeat interval to {interval_min} minute(s)")

    def enable_one_node(self, imaging_node_list: list, fc_deployment_logger):
        """Enable one node after imaging
           This is a workaround for enabling one node in nodes whihc are imaged in FC. This funcion execution can be ignored in production

        Args:
            imaging_node_list (list): List of node details to be imaged
            fc_deployment_logger (Object): Logger object to be used to log the output
        """
        self.logger.info("Enabling one node support for re-imaged nodes...")
        update_fc_hearbeat_interval = BatchScript(parallel=True, max_workers=10)
        for deployment_data in imaging_node_list:
            for node in deployment_data["nodes_list"]:
                update_fc_hearbeat_interval.add(EnableOneNode(node["cvm_ip"], "nutanix", "nutanix/4u",
                                                              fc_deployment_logger=fc_deployment_logger))
        result = update_fc_hearbeat_interval.run()
        self.logger.debug(result)
        self.logger.info("Enabled one node support")

    def imaging_nodes_deployment(self, block_name, site_name, imaging_nodes_list):
        """Image only nodes in Foundation Central

        Args:
            block_name (str): Name of the block
            site_name (str): Name of the Site
            imaging_nodes_list (_type_): List of nodes to be imaged
        """
        # Giving a name to imaging nodes deployment for progress tracking
        for index, cluster_data in enumerate(imaging_nodes_list):
            cluster_data["cluster_name"] = "imaging_nodes_set_{0}".format(index)
        self.logger.debug(f"imaging_nodes_list: {imaging_nodes_list}")
        self.logger.info("Starting nodes imaging in FC...")
        now = datetime.datetime.now()
        self.logger.info(f"{site_name }: Imaging Nodes Start time: {now}")
        log_file = f"{block_name}_{site_name}_node_imaging.log"
        fc_deployment_logger = get_logger(log_file, file_name=log_file)
        result, error = self.fc_deployment(imaging_nodes_list, block_name, site_name, fc_deployment_logger)
        if error:
            return False, error
        if result:
            now = datetime.datetime.now()
            self.logger.info(f"{site_name }: Imaging Nodes End time: {now}")
            if result["failed_count"] >= 1:
                # TODO: Check the nodes which all passed and deploy only those nodes
                #       Remove the failed nodes and deploy the rest of the nodes
                return False, "Imaging Failed. Please check the result"
            elif result["in-progess"] >= 1:
                return False, "Imaging is still in-progess for long time. Please check the result."
            # Update the heartbeat interval, so the nodes are dicovered soon in the Foundation Central
            else:
                self.logger.debug("Updating heartbeat interval...")
                self.update_heartbeat_interval(imaging_nodes_list, fc_deployment_logger=fc_deployment_logger)
                # Enabling one node is not required in production
                self.logger.debug("Enabling one node support...")
                self.enable_one_node(imaging_nodes_list, fc_deployment_logger)
            self.logger.info("Sleep 5 mins for the nodes to be discovered")
            time.sleep(5 * 60)
        self.logger.info("Imaging nodes completed")
        return True, None

    def deploy_site(self, block_name, site_config):
        """Deploy clusters in block-sites

        Args:
            block_name (str): Name of pod-block
            site_config (_type_): Site configuration
        """
        site_name = site_config["site_name"]
        self.logger.info(f"Start deployment for site {site_name}")
        self.site_data = site_config
        self.site_data["aos_versions"] = self.data["aos_versions"]
        self.site_data["hypervisors"] = self.data["hypervisors"]
        self.site_data["global_network"] = self.data["global_network"]

        # Get AOS & Hypervisor urls and update in site data
        get_aos_url_mapping(self.site_data)
        get_hypervisor_url_mapping(self.site_data)

        # Gather Cluster data for the site
        imaging_nodes_list, cluster_data_list = self.get_site_cluster_data()
        self.logger.debug(f"imaging_nodes_list: {imaging_nodes_list}")
        self.logger.debug(f"cluster_data_list: {cluster_data_list}")

        imaging_error = None
        # Imaging nodes in Foundation central
        if imaging_nodes_list:
            _, imaging_error = self.imaging_nodes_deployment(block_name, site_name, imaging_nodes_list)
            if imaging_error:
                self.exceptions.append(imaging_error)

        # TODO: Add node available check in Monitor fc deployment
        # Remove the failed nodes and deploy rest of the nodes
        if cluster_data_list and not imaging_error:
            now = datetime.datetime.now()
            self.logger.info(f"{site_name }: Cluster Creation Start time: {now}")
            log_file = f"{block_name}_{site_name}_deployments.log"
            fc_deployment_logger = get_logger(log_file, file_name=log_file)
            result, error = self.fc_deployment(cluster_data_list, block_name, site_name, fc_deployment_logger)
            now = datetime.datetime.now()
            self.logger.info(f"{site_name }: Cluster Creation End time: {now}")
            if error:
                self.exceptions.append(error)
            else:
                self.block_result[block_name][site_name] = result
                self.overall_result.update(self.block_result)
        else:
            self.logger.warning(f"No clusters to deploy in site {site_name}")

    def execute(self, **kwargs):
        """Run Image cluster nodes for multiple sites
        """
        self.logger.debug(self.data)
        self.assigned_nodes = []
        self.overall_result = {}

        # Looping through blocks
        for block_info in self.data["pod"]["pod_blocks"]:
            block_name = block_info["pod_block_name"]
            self.block_result = {block_name: {}}
            try:
                self.logger.info(f"Start deployment for block {block_name}")
                self.pc_session = RestAPIUtil(
                    block_info["pc_ip"], user=block_info["pc_username"],
                    pwd=block_info["pc_password"], port="9440", secured=True)
                self.image_node = ImagedNode(self.pc_session)

                # Looping through sites
                for site_config in block_info["edge-sites"]:
                    self.deploy_site(block_name, site_config)
            except Exception as e:
                self.exceptions.append(e)
        self.logger.info(json.dumps(self.overall_result, indent=2))

    def verify(self):
        pass

    @staticmethod
    def get_netmask_gateway(network, node: dict):
        """Get the Netmask Gateway for Management and IPMI network

        Args:
            network (dict): Management & IPMI network
            node (dict): Discovered Node detail

        Returns:
            tuple: Netmask Gateway for management & IPMI network
        """
        mgmt_netmask = network["mgmt_netmask"] if network["mgmt_netmask"] else node["mgmt_netmask"]
        mgmt_gateway = network["mgmt_gateway"] if network["mgmt_gateway"] else node["mgmt_gateway"]
        ipmi_netmask = network["ipmi_netmask"] if network["ipmi_netmask"] else node["ipmi_netmask"]
        ipmi_gateway = network["ipmi_gateway"] if network["ipmi_gateway"] else node["ipmi_gateway"]
        return mgmt_netmask, mgmt_gateway, ipmi_netmask, ipmi_gateway
