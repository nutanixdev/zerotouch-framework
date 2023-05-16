from scripts.python.cluster_script import ClusterScript
from scripts.python.helpers.v1.container import Container
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class CreateContainerPe(ClusterScript):
    """
    Create Storage container in the give clusters
    """
    def __init__(self, data: dict, **kwargs):
        super(CreateContainerPe, self).__init__(data, **kwargs)

    def execute_single_cluster(self, cluster_ip: str, cluster_details: dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]

        try:
            if cluster_details.get("containers"):
                for container in cluster_details["containers"]:
                    container_op = Container(pe_session)
                    # todo pre-checks if they are valid
                    container_op.create(**container)
            else:
                logger.info(f"No containers specified in '{cluster_ip}/ {cluster_details['cluster_info']['name']}'."
                            " Skipping...")
        except Exception as e:
            cluster_info = f"'{cluster_ip}/ {cluster_details['cluster_info']['name']}'"
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info} with the error: {e}")
            return

    def verify(self):
        # todo do we need to verify these?
        pass
