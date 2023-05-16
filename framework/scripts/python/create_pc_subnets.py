from helpers.log_utils import get_logger
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.helpers.v3.cluster import Cluster as PcCluster
from scripts.python.helpers.v3.network import Network
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateSubnetsPc(Script):
    """
    Class that creates subnets in PC
    """

    def __init__(self, data: dict):
        self.task_uuid_list = []
        self.data = data
        self.pc_session = self.data["pc_session"]
        # pass the Cluster Objects
        # create_pe_pc helper function can be used
        self.pe_clusters = self.data.get("clusters", {})
        super(CreateSubnetsPc, self).__init__()

    def execute(self, **kwargs):
        try:
            network = Network(session=self.pc_session)
            subnets_to_create = []

            for _, cluster_details in self.pe_clusters.items():
                for subnet_info in cluster_details.get("networks", []):
                    cluster_name = cluster_details["cluster_info"]["name"]
                    cluster_uuid = cluster_details["cluster_info"].get("uuid")

                    if not cluster_uuid:
                        pc_cluster = PcCluster(self.pc_session)
                        pc_cluster.get_pe_info_list()
                        cluster_uuid = pc_cluster.name_uuid_map.get(cluster_name)
                        if not cluster_uuid:
                            self.exceptions.append(f"Failed to create subnets in {cluster_name}")
                            continue

                    filter_criteria = f"cluster_name=={cluster_name};vlan_id=={subnet_info['vlan_id']}"

                    subnets_response = network.list(filter=filter_criteria)

                    if len(subnets_response) > 0:
                        logger.warning(f"Skipping Subnet creation. Subnet {subnet_info['name']} with vlanId "
                                       f"{subnet_info['vlan_id']}, already exists in the cluster {cluster_name}")
                    else:

                        try:
                            # add cluster_uuid
                            payload = network.create_pc_subnet_payload(cluster_uuid=cluster_uuid, **subnet_info)
                            subnets_to_create.append(payload)
                        except Exception as e:
                            self.exceptions.append(f"Failed to create subnets {subnet_info['name']}: {e}")

            if not subnets_to_create:
                logger.warning(f"No subnets to create in {self.data['pc_ip']}")
                return

            logger.info(f"Batch create subnets in {self.data['pc_ip']}")
            self.task_uuid_list = network.batch_create_network(subnets_to_create)
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if self.task_uuid_list:
            app_response, status = PcTaskMonitor(self.pc_session,
                                                 task_uuid_list=self.task_uuid_list).monitor()

            if app_response:
                self.exceptions.append(f"Some tasks have failed. {app_response}")

            if not status:
                self.exceptions.append("Timed out. Creation of subnets in PC didn't happen in the prescribed timeframe")
