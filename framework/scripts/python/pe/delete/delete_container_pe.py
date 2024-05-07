from typing import Dict
from framework.scripts.python.pe.cluster_script import ClusterScript
from framework.scripts.python.helpers.v1.container import Container
from framework.helpers.log_utils import get_logger

logger = get_logger(__name__)


class DeleteContainerPe(ClusterScript):
    """
    Delete Storage container in PE
    """

    def __init__(self, data: Dict, **kwargs):
        super(DeleteContainerPe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
                'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("containers"):
                container_op = Container(pe_session)

                # check if container exists
                container_list = container_op.read()
                container_name_id_dict = {container["name"]: container["id"] for container in container_list}

                for container_to_delete in cluster_details["containers"]:
                    if container_to_delete.get("name") not in container_name_id_dict.keys():
                        self.logger.warning(f"Container {container_to_delete['name']} doesn't exist!")
                        continue

                    self.logger.info(f"Deleting container {container_to_delete['name']!r} in {cluster_info!r}")
                    response = container_op.delete(endpoint=container_name_id_dict[container_to_delete['name']])

                    if response.get("value"):
                        self.logger.info(f"Deletion of Storage container {container_to_delete.get('name')} successful!")
                    else:
                        raise Exception(f"Could not delete the Storage container. Error: {response}")
            else:
                self.logger.info(f"No containers specified in {cluster_info!r}. Skipping...")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if containers were deleted
        try:
            self.results["clusters"][cluster_ip] = {"Delete_container": {}}
            if not cluster_details.get("containers"):
                return

            pe_session = cluster_details["pe_session"]

            container_obj = Container(pe_session)
            container_list = []
            container_name_list = []
            self.results["clusters"][cluster_ip] = {"Delete_container": {}}

            for container in cluster_details.get("containers"):
                # Set default status
                self.results["clusters"][cluster_ip]["Delete_container"][container["name"]] = "CAN'T VERIFY"

                container_list = container_list or container_obj.read()
                container_name_list = container_name_list or [container.get("name") for container in container_list]

                if container["name"] not in container_name_list:
                    self.results["clusters"][cluster_ip]["Delete_container"][container["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Delete_container"][container["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip!r}")
