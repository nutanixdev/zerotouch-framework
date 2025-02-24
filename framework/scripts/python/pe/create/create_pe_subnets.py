from typing import Dict
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v2.network import Network
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class CreateSubnetPe(ClusterScript):
    """
    Class that creates subnets in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(CreateSubnetPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("networks"):
                network_op = Network(session=pe_session)

                for network_to_create in cluster_details["networks"]:
                    try:
                        self.logger.info(f"Creating a new network {network_to_create['name']!r} in {cluster_info!r}")
                        response = network_op.create(**network_to_create)

                        if response.get("network_uuid"):
                            self.logger.info(f"Creation of network {network_to_create.get('name')} successful!")
                        else:
                            raise Exception(f"Could not create the network. Error: {response}")
                    except Exception as e:
                        self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                               f"{cluster_info!r} with the error: {e}")
            else:
                self.logger.info(f"No Networks specified in {cluster_info!r}. Skipping...")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if network is created in PE
        try:
            if not cluster_details.get("networks"):
                return

            self.results["clusters"][cluster_ip] = {"Create_Network": {}}
            pe_session = cluster_details["pe_session"]

            network_obj = Network(pe_session)
            network_list = []

            for network in cluster_details.get("networks"):
                # Set default status
                self.results["clusters"][cluster_ip]["Create_Network"][network["name"]] = "CAN'T VERIFY"

                network_list = network_list or network_obj.read()
                network_vlanid_list = [network.get("vlan_id") for network in network_list]

                if network["vlan_id"] in network_vlanid_list:
                    self.results["clusters"][cluster_ip]["Create_Network"][network["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Create_Network"][network["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
