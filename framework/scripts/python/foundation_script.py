import sys
import socket
import struct
from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.fc.imaged_nodes import ImagedNode
from scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from scripts.python.script import Script
from scripts.python.image_cluster_script import ImageClusterScript
from scripts.python.helpers.batch_script import BatchScript


logger = get_logger(__name__)


class FoundationScript(Script):

    def __init__(self, data: dict):
        self.data = data
        self.data["pc_session"] = RestAPIUtil(
            data["pc_ip"], user=data["pc_username"],
            pwd=data["pc_password"], port="9440", secured=True)
        self.image_node = ImagedNode(self.data["pc_session"])
        self.mgmt_static_ips = {}
        self.ipmi_static_ips = {}
        super(FoundationScript, self).__init__()

    def ip_dict(self, total_cluster_size: int, ip_range: list, ip_category: str, cluster_name: str = ""):
        """Returns list of IP Dictionaries within the given IP range

        Args:
            total_cluster_size (int): Cluster size
            ip_range (str): ip range to separated by -
            ip_category (str): IP category: management or ipmi

        Returns:
            list: list of IP Dictionaries within the given IP range
        """
        if ip_range:
            start = struct.unpack('>I', socket.inet_aton(ip_range[0]))[0]
            end = struct.unpack('>I', socket.inet_aton(ip_range[-1]))[0]
            ip_list = [socket.inet_ntoa(struct.pack('>I', i)) for i in range(start, end+1)]
            error = self.validate_ip(total_cluster_size, len(ip_list), ip_category, cluster_name)
            if error:
                return None, error
            ip_dict = {ip: True for ip in ip_list}
            return ip_dict, ""
        else:
            return {}, ""

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
            logger.error("No Free IP available")
            return None

    def get_cluster_ip_mappings(self, cluster_info: dict, cluster_name: str):
        """Populate static ip dictionary with the provided ip range for each cluster or site

        Args:
            cluster_info (dict): Cluster information provided

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
                    logger.info("Got {} available node details".format(len(node_details)))
                    logger.debug("Node details: {}".format(node_details))
                    return node_details, None
        else:
            return None, "Not enough available nodes found in block serials."

    def update_node_details(self, node_list: list, cluster_name: str, cluster_info: dict):
        """Update the node details with provided site details

        Args:
            node_list (list): List of node details with updated params
        """
        updated_node_list = []
        if cluster_info.get("re-image", self.data["re-image"]) and cluster_info["cluster_size"] == 1:
            logger.warning("Re-imaging for 1 node is not supported. Creating cluster {} without imaging.".format(cluster_name))
        for node in node_list:
            if not cluster_info.get("use_existing_network_settings", self.data["use_existing_network_settings"]):
                network = cluster_info["network"] if cluster_info.get("network", None) else self.data["network"]
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
                    "cvm_vlan_id": cluster_info.get("cvm_vlan_id", None),
                    "hypervisor_type": self.data["imaging_parameters"]["hypervisor_type"],
                    "image_now": cluster_info.get("re-image", self.data.get("re-image", False)) if cluster_info["cluster_size"] > 1 else False,
                    "ipmi_ip": self.get_free_ip(cluster_info["ipmi_static_ips"], self.ipmi_static_ips) if cluster_info["ipmi_static_ips"] else node["ipmi_ip"],
                    "cvm_ram_gb": cluster_info.get("cvm_ram", 12),
                    "use_existing_network_settings": False,
                    "ipmi_gateway": ipmi_gateway,
                }
            elif cluster_info.get("use_existing_network_settings", self.data["use_existing_network_settings"]):
                node_spec = {
                    "use_existing_network_settings": True,
                    "imaged_node_uuid": node["imaged_node_uuid"],
                    "image_now": cluster_info.get("re-image", self.data.get("re-image", False)) if cluster_info["cluster_size"] > 1 else False,
                    }
            node.update(node_spec)
            updated_node_list.append(node)
        return updated_node_list

    def update_aos_ahv_spec(self):
        """Update hypervisor iso details
        """
        return {
            "aos_package_url": self.data["aos_url"],
            "hypervisor_iso_details": {
                "hypervisor_type": self.data["imaging_parameters"]["hypervisor_type"],
                "url": self.data["hypervisor_url"]
            }
        }

    def update_common_network_settings(self):
        """ Update common network settings
        """
        return {
            "cvm_dns_servers": self.data["global_network"]["dns_servers"],
            "hypervisor_dns_servers": self.data["global_network"]["dns_servers"],
            "cvm_ntp_servers": self.data["global_network"]["ntp_servers"],
            "hypervisor_ntp_servers": self.data["global_network"]["ntp_servers"],
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
            if node["node_serial"] in node_serial_list:
                node_details.append(node)
                self.node_list.remove(node)
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
            if cluster_info.get("re-image", self.data["re-image"]) and cluster_info["cluster_size"] > 1:
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
            logger.error(error)
            sys.exit(1)
        if self.node_list:
            self.imaging = ImagedCluster(self.data["pc_session"])
            for cluster_name, cluster_info in self.data["clusters"].items():
                if cluster_info.get("node_serials", None):
                    node_serial_cluster_data[cluster_name] = cluster_info
                else:
                    block_serial_cluster_data[cluster_name] = cluster_info
                if not cluster_info.get("network"):
                    # Calculating total cluster size to check sufficient management & ipmi IPs
                    total_cluster_size += cluster_info["cluster_size"]
            common_network_settings = self.update_common_network_settings()

            # Adding node_serail & block_serial cluster data to ordered dict, the cluster with node serial will be added first for cluster deployment
            site_cluster_info = {}
            site_cluster_info.update(node_serial_cluster_data)

            # Get the static ip list for site static ip list
            static_ip_error = None
            if not self.data["use_existing_network_settings"]:
                self.mgmt_static_ips, mgmt_ip_error = self.ip_dict(total_cluster_size, self.data["network"]["mgmt_static_ips"], ip_category="management")
                self.ipmi_static_ips, ipmi_ip_error = self.ip_dict(total_cluster_size, self.data["network"]["ipmi_static_ips"], ip_category="ipmi")
                if mgmt_ip_error or ipmi_ip_error:
                    static_ip_error = mgmt_ip_error+ipmi_ip_error
                    self.exceptions.append("Skipping Cluster deployment which shares site level netowrk. Reason: {}".format(static_ip_error))
            # Exclusing cluster deployment which share site level netowrk for deployment if there is static ip error
            if not static_ip_error:
                site_cluster_info.update(block_serial_cluster_data)

            # todo: order block_serial_cluster_data based on cluster size
            # block_serial_cluster_data = sorted(block_serial_cluster_data.items(), key=lambda x: x[1]['cluster_size'], reverse=False)

            # Get the nodes based on block serials provided
            node_list, error = self.image_node.node_details_by_block_serial(self.data["blocks_serial_numbers"])
            if error:
                self.exceptions.append(error)
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
            return cluster_data_list

    def execute(self, **kwargs):
        """Run Image cluster nodes
        """
        logger.debug(self.data)
        self.assigned_nodes = []
        cluster_data_list = self.get_site_cluster_data()
        image_cluster_script = BatchScript(parallel=True)
        for cluster_data in cluster_data_list:
            image_cluster_script.add(ImageClusterScript(data=self.data, cluster_data=cluster_data, imaging_obj=self.imaging))
        image_cluster_script.run()

    def verify(self):
        pass

    @staticmethod
    def validate_redundancy_factor(cluster_size: int, redundancy_factor: int):
        """Validate the redundancy factor for a given cluster based on cluster size and redundancy factor

        Args:
            cluster_size (int): Cluster size
            redundancy_factor (int): Redundancy factor
        """
        if redundancy_factor not in [2, 3]:
            logger.error('Invalid redundancy factor {}. Nutanix supports redundancy factor 2, and also redundancy factor 3 only if the cluster has 5+ nodes'.format(redundancy_factor))
            sys.exit(1)
        elif redundancy_factor == 3 and cluster_size < 5:
            logger.error('With redundancy factor {0}, cluster size must be 5 or more and you selected {1} which is not compatible!'.format(redundancy_factor, cluster_size))
            sys.exit(1)

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
