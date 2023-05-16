import sys
import time
from scripts.python.script import Script
from scripts.python.helpers.fc.imaged_clusters import ImagedCluster
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class ImageClusterScript(Script):
    """
    Foundation Central Image Cluster Script
    """
    def __init__(self, data: dict, cluster_data: dict, imaging_obj: ImagedCluster = None):
        """
        Args:
            data (dict): proved json data
            cluster_data (dict): Updated cluster data
            imaging_obj (object, optional): Imaging cluster object. Defaults to None.
        """
        self.data = data
        self.cluster_data = cluster_data
        if imaging_obj:
            self.imaging = imaging_obj
        else:
            self.imaging = ImagedCluster(self.data["pc_session"])
        super(ImageClusterScript, self).__init__()

    def execute(self):
        """
        Run Image cluste nodes in Foundation Central
        """
        spec, error = self.imaging.get_spec(params=self.cluster_data)
        if error:
            self.exceptions.append("Failed generating Image Nodes Spec: {}".format(error))
            sys.exit(1)
        logger.debug("Image Node Spec: {}".format(spec))
        resp = self.imaging.create(spec)
        self.imaged_cluster_uuid = resp["imaged_cluster_uuid"]
        logger.debug("imaged_cluster_uuid for cluster {}: {}".format(
            self.cluster_data["cluster_name"], self.imaged_cluster_uuid))

    def verify(self):
        """
        Verify Cluster deployment status
        """
        state = ""
        delay = 60
        logger.info("Wait for 15 minutes to monitor cluster {} status".format(self.cluster_data["cluster_name"]))
        time.sleep(15 * 60)
        timeout = time.time() + (3 * 60 * 60)
        while state != "COMPLETED":
            response = self.imaging.read(self.imaged_cluster_uuid)
            stopped = response["cluster_status"]["imaging_stopped"]
            aggregate_percent_complete = response["cluster_status"][
                "aggregate_percent_complete"
            ]
            if stopped:
                if aggregate_percent_complete < 100:
                    message = "Imaging/Creation stopped/failed before completion. See below details for deployment status:"
                    status = self._get_progress_error_status(response, message)
                    logger.error(status)
                else:
                    message = "Imaging/Creation Completed."
                    status = self._get_progress_error_status(response, message)
                    logger.info(status)
                state = "COMPLETED"
            else:
                state = "PENDING"
                status = self._get_progress_error_status(response)
                if time.time() > timeout:
                    message = "Failed to poll on image node progress. Reason: Timeout\nStatus: "
                    status = self._get_progress_error_status(response, message)
                logger.info(status)
                time.sleep(delay)

    def _get_progress_error_status(self, progress: dict, message: str = ""):
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
                res += "\n\tnode_uuid: {0}\n".format(node[entity_name])
                res += "\tstatus: {0}\n".format(node["status"])
                if node.get("message_list"):
                    res += "\tmessage: {0}\n".format("\n".join(node["message_list"]))
        return res
