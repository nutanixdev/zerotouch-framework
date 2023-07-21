import time
import logging
from helpers.rest_utils import RestAPIUtil
from scripts.python.script import Script
from scripts.python.helpers.fc.imaged_clusters import ImagedCluster


class MonitorDeployment(Script):
    """
    Monitor Deployments in Foundation Central
    """
    def __init__(self, pc_session: RestAPIUtil, cluster_name: str, imaged_cluster_uuid: str, fc_deployment_logger: logging.getLogger):
        """
        Args:
            pc_session (str): PC Session object
            cluster_name (str): Cluster name
            imaged_cluster_uuid (dict): Imaged cluster uuid
            fc_deployment_logger (Object, optional): Logger object to be used to log the output
        """
        self.imaged_cluster_uuid = imaged_cluster_uuid
        self.cluster_name = cluster_name
        self.imaging = ImagedCluster(pc_session)
        super(MonitorDeployment, self).__init__()
        self.logger = fc_deployment_logger

    def execute(self):
        """
        Run Image cluste nodes in Foundation Central
        """
        state = ""
        delay = 60
        timeout = time.time() + (3 * 60 * 60)
        self.logger.warning(self.imaged_cluster_uuid)
        while state not in ["COMPLETED", "FAILED"]:
            response = self.imaging.read(self.imaged_cluster_uuid)
            stopped = response["cluster_status"]["imaging_stopped"]
            aggregate_percent_complete = response["cluster_status"]["aggregate_percent_complete"]
            if stopped:
                if aggregate_percent_complete < 100:
                    message = f"{self.cluster_name} Imaging/Creation stopped/failed before completion. See below details for deployment status:"
                    status = self._get_deployment_status(response, message)
                    self.logger.error(status)
                    state = "FAILED"
                else:
                    message = f"{self.cluster_name} Imaging/Creation Completed."
                    status = self._get_deployment_status(response, message)
                    self.logger.info(status)
                    state = "COMPLETED"
            else:
                state = "PENDING"
                status = self._get_deployment_status(response)
                if time.time() > timeout:
                    message = f"Failed to poll on image node progress for cluster {self.cluster_name}. Reason: Timeout\nStatus: "
                    status = self._get_deployment_status(response, message)
                self.logger.debug(status)
                self.logger.info(f"Cluster {self.cluster_name} Deployment Percentage Complete: {aggregate_percent_complete}")
                time.sleep(delay)
        self.results = {self.cluster_name: {"result": state, "status": status, "imaged_cluster_uuid": self.imaged_cluster_uuid}}

    def verify(self):
        pass

    def _get_deployment_status(self, progress: dict, message: str = ""):
        """Get the status of node and cluster progress

        Args:
            progress (dict): Response dict
            message (str, optional): Message to add while displaying status. Defaults to "".

        Returns:
            str: Status of node and cluster progress
        """
        return "{0}\nClusters: {1}\nNodes: {2}".format(
            message,
            self._get_cluster_progress_messages(
                progress, "cluster_progress_details", "cluster_name"
            ),
            self._get_node_progress_messages(
                progress, "node_progress_details", "imaged_node_uuid"
            ),
        )

    def _get_cluster_progress_messages(self, progress: dict, entity_type: str, entity_name: str):
        """Cluster progress messages

        Args:
            progress (dict): Response dictionary
            entity_type (str): Entity type to filter
            entity_name (str): Entity name to filter

        Returns:
            str: Cluster progress messages
        """
        res = ""
        cluster = progress["cluster_status"][entity_type]
        if cluster is not None:
            if cluster.get(entity_name):
                res += "\n\tcluster_name: {0}\n".format(cluster[entity_name])
            if cluster.get("status"):
                res += "\tstatus: {0}\n".format(cluster["status"])
            if cluster.get("message_list"):
                res += "\tmessage: {0}\n".format("\n".join(cluster["message_list"]))
        return res

    def _get_node_progress_messages(self, progress: dict, entity_type: str, entity_name: str):
        """Node progress messages

        Args:
            progress (dict): Response dictionary
            entity_type (str): Entity type to filter
            entity_name (str): Entity name to filter

        Returns:
            str: Node progress messages
        """
        res = ""
        nodes = progress["cluster_status"][entity_type]
        if nodes:
            for node in nodes:
                # res += "\n\tnode_uuid: {0}\n".format(node[entity_name])
                res += "\tstatus: {0}\n".format(node["status"])
                if node.get("message_list"):
                    res += "\tmessage: {0}\n".format("\n".join(node["message_list"]))
        return res
