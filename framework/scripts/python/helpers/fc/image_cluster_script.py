import logging
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.script import Script
from .imaged_clusters import ImagedCluster


class ImageClusterScript(Script):
    """
    Foundation Central Image Cluster Script
    """
    def __init__(self, pc_session: RestAPIUtil, cluster_data: dict, fc_deployment_logger: logging.getLogger):
        """
        Args:
            data (dict): proved json data
            cluster_data (dict): Updated cluster data
            fc_deployment_logger (Object, optional): Logger object to be used to log the output
        """
        self.cluster_data = cluster_data
        self.imaging = ImagedCluster(pc_session)
        super(ImageClusterScript, self).__init__()
        self.logger = fc_deployment_logger

    def execute(self):
        """
        Run Image cluster nodes in Foundation Central
        """
        cluster_name = self.cluster_data["cluster_name"]
        self.logger.info(f"Running Image cluster nodes in Foundation Central {cluster_name}")
        spec, error = self.imaging.get_spec(params=self.cluster_data)
        if error:
            self.exceptions.append("Failed generating Image Nodes Spec: {}".format(error))
            self.logger.error("Failed generating Image Nodes Spec: {}".format(error))
        else:
            self.logger.debug(f"Cluster {cluster_name} Image Node Spec: {spec}")
            try:
                resp = self.imaging.create(spec)
                self.results = {cluster_name: resp["imaged_cluster_uuid"]}
                self.logger.debug(f"imaged_cluster_uuid for cluster {cluster_name}: {resp['imaged_cluster_uuid']}")
                self.logger.info("{0} is the imaged cluster uuid for {1} FC deployment".format(resp['imaged_cluster_uuid'], cluster_name))
            except Exception as e:
                self.exceptions.append(f"Failed to deploy cluster {cluster_name}. Error: {e}")

    def verify(self):
        pass
