import time

from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from .state_monitor import StateMonitor
from ..ndb.clusters import Cluster
from ..ndb.ha import HA

logger = get_logger(__name__)


class NdbUploadJsonMonitor(StateMonitor):
    """
    Class to wait for json to be uploaded to NDB cluster
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 10
    DEFAULT_TIMEOUT_IN_SEC = 60

    def __init__(self, session: RestAPIUtil, cluster_id: str, cluster_ip: str, username: str, password: str,
                 skip_upload: str = "false", skip_profile: str = "true", update_json: str = "true"):
        """
          The constructor for NdbUploadJsonMonitor
          Args:
            session: request session to query the API
            cluster_id(str): The id of the cluster
            cluster_ip(str): The ip address of the cluster
            username(str): The username of the cluster
            password(str): The password of the cluster
            skip_upload(str): Whether to skip upload
            skip_profile(str): Whether to skip profile
            update_json(str): Whether to update json
          """
        self.session = session
        self.cluster_info = {
            "cluster_id": cluster_id,
            "cluster_ip": cluster_ip,
            "username": username,
            "password": password,
            "skip_upload": skip_upload,
            "skip_profile": skip_profile,
            "update_json": update_json
        }
        self.cluster_op = Cluster(self.session)

    def check_status(self):
        """
        Check whether json is uploaded to NDB cluster

        Returns:
          bool: True
        """
        response = None
        completed = False

        try:
            _ = self.cluster_op.set_cluster_json(**self.cluster_info)
            time.sleep(5)
            response = self.cluster_op.get_cluster_json(self.cluster_info["cluster_id"])
            if response:
                completed = True
            else:
                logger.info(f"Waiting for json to be uploaded to NDB cluster {self.cluster_info['name']}...")
        except Exception as e:
            logger.error(f"Error while checking NDB json upload status: {e}")

        return response, completed
