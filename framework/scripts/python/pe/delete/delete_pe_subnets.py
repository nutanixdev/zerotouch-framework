from typing import Dict
from collections import defaultdict

from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v2.network import Network
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)

class DeleteSubnetsPe(ClusterScript):
    """
    Class that deletes subnets in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(DeleteSubnetsPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']!r}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip!r}"
        try:
            if cluster_details.get("networks"):
                network_op = Network(session=pe_session)
                network_list = network_op.read()
                
                exisiting_networks_uuid_dict = {}
                uuids_list = []
                for network in network_list:
                    if network.get('name') in exisiting_networks_uuid_dict.keys():
                        exisiting_networks_uuid_dict[network['name']].append(
                            network.get('uuid')
                        )
                    else:
                        exisiting_networks_uuid_dict[network['name']] = [network.get('uuid')]
                    uuids_list.append(network['uuid'])

                for network_to_delete in cluster_details['networks']:
                    if 'uuid' in network_to_delete:
                        if network_to_delete['uuid'] not in uuids_list:
                            self.logger.warning(
                                f"network with uuid: {network_to_delete['uuid']!r} does not exist! Skipping"
                            )
                            continue

                        self.logger.info(f"Deleting network with uuid'{network_to_delete['uuid']}' in {cluster_info}")
                        response = network_op.delete(endpoint=network_to_delete['uuid'])

                        if response.ok:
                            self.logger.info(f"Deletion of network {network_to_delete['uuid']!r} successful!")
                        else:
                            raise Exception(f"Could not Delete the network. Error: {response}")

                    else:
                        #Check if given Name Id Exists in the given Cluster
                        if network_to_delete['name'] not in exisiting_networks_uuid_dict.keys():
                            self.logger.warning(
                                f"network with name: {network_to_delete['name']!r} does not exist! Skipping"
                            )
                            continue

                        try:
                            for uuid in exisiting_networks_uuid_dict[network_to_delete['name']]:
                                self.logger.info(f"Deleting network {network_to_delete['name']!r} and uuid {uuid!r} in {cluster_info}")
                                response = network_op.delete(endpoint=uuid)
                                if response.ok:
                                    self.logger.info(f"Deletion of network {network_to_delete['name']!r} and uuid {uuid!r} successful!")
                                else:
                                    raise Exception(f"Could not Delete the network. Error: {response}")
                        except Exception as e:
                            self.exceptions.append(
                                f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}"
                            )
            else:
                self.logger.info(f"No Networks specified in '{cluster_info}'. Skipping...")

        except Exception as e:
            self.exceptions.append(
                f"{type(self).__name__} failed for the cluster {cluster_info} with the error: {e}"
            )
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if network is Deleted in PE
        try:
            self.results["clusters"][cluster_ip] = {"Delete_Network": {}}
            if not cluster_details.get("networks"):
                return

            pe_session = cluster_details["pe_session"]

            network_obj = Network(pe_session)
            network_list = []

            network_list = network_list or network_obj.read()
            network_name_list = [str(network.get("name")) for network in network_list]
            uuid_list = [str(network.get("uuid")) for network in network_list]
            for network in cluster_details.get("networks"):
                # Set default status
                if 'uuid' in network:
                    self.results["clusters"][cluster_ip]["Delete_Network"][network["uuid"]] = "CAN'T VERIFY"                
                    if network["uuid"] not in uuid_list:
                        self.results["clusters"][cluster_ip]["Delete_Network"][network["uuid"]] = "PASS"
                    else:
                        self.results["clusters"][cluster_ip]["Delete_Network"][network["uuid"]] = "FAIL"
                else:
                    self.results["clusters"][cluster_ip]["Delete_Network"][network["name"]] = "CAN'T VERIFY"
                    if network["name"] not in network_name_list:
                        self.results["clusters"][cluster_ip]["Delete_Network"][network["name"]] = "PASS"
                    else:
                        self.results["clusters"][cluster_ip]["Delete_Network"][network["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
