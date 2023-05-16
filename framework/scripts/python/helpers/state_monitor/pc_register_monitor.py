from helpers.log_utils import get_logger
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from scripts.python.helpers.v3.cluster import Cluster as PcCluster

logger = get_logger(__name__)


class PcRegisterMonitor(StateMonitor):
    """
    The class to wait for blueprint launch status to come in expected state
    """
    DEFAULT_CHECK_INTERVAL_IN_SEC = 30
    DEFAULT_TIMEOUT_IN_SEC = 10 * 60

    def __init__(self, session: RestAPIUtil, **kwargs):
        """
          The constructor for PcRegisterMonitor
          Args:
            kwargs:
              session: request session to query the API
              pe_uuids(list): List of UUIDs of PE clusters to be verified
          """
        self.session = session
        self._pe_uuids = kwargs.get('pe_uuids')

    def check_status(self):
        """
        Check whether newly registered PE's show up in PC

        Returns:
          bool: True
        """
        pc_cluster = PcCluster(self.session)
        pc_cluster.get_pe_info_list()
        pc_cluster_uuids = pc_cluster.name_uuid_map.values()

        if not pc_cluster_uuids:
            return pc_cluster_uuids, False

        cluster_sync_complete = True
        for pe_uuid in self._pe_uuids:
            if pe_uuid not in pc_cluster_uuids:
                cluster_sync_complete = False
        return pc_cluster_uuids, cluster_sync_complete
