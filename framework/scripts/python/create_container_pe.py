from typing import Dict
from .cluster_script import ClusterScript
from .helpers.v1.container import Container
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class CreateContainerPe(ClusterScript):
    """
    Create Storage container in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(CreateContainerPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"

        try:
            if cluster_details.get("containers"):
                container_op = Container(pe_session)

                # check if already exists
                container_list = container_op.read()
                container_name_list = [container.get("name") for container in container_list]

                for container_to_create in cluster_details["containers"]:
                    if container_to_create.get("name") in container_name_list:
                        self.logger.warning(f"Container {container_to_create['name']} already exists!")
                        continue

                    self.logger.info(f"Creating new container '{container_to_create['name']}' in {cluster_info}")
                    response = container_op.create(**container_to_create)

                    if response["value"]:
                        self.logger.info(f"Creation of Storage container {container_to_create.get('name')} successful!")
                    else:
                        raise Exception(f"Could not create the Storage container. Error: {response}")
            else:
                self.logger.info(f"No containers specified in '{cluster_info}'. Skipping...")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if containers were created
        try:
            self.results["clusters"][cluster_ip] = {"Create_container": {}}
            if not cluster_details.get("containers"):
                return

            pe_session = cluster_details["pe_session"]

            container_obj = Container(pe_session)
            container_list = []
            container_name_list = []
            self.results["clusters"][cluster_ip] = {"Create_container": {}}

            for container in cluster_details.get("containers"):
                # Set default status
                self.results["clusters"][cluster_ip]["Create_container"][container["name"]] = "CAN'T VERIFY"

                container_list = container_list or container_obj.read()
                container_name_list = container_name_list or [container.get("name") for container in container_list]

                if container["name"] in container_name_list:
                    self.results["clusters"][cluster_ip]["Create_container"][container["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Create_container"][container["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of '{type(self).__name__}' for {cluster_ip}")
