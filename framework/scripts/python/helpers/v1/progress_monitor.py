from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class ProgressMonitor(PeEntityV1):
    """
    v1 version of progress monitor
    """
    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/progress_monitors"
        self.session = session
        super(ProgressMonitor, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def get_progress_monitors(self, start_time: int | float) -> dict:
        query = {
            "hasSubTaskDetail": False,
            "count": 500,
            "page": 1,
            "filterCriteria": f"internal_task==false;(status==kSucceeded);last_updated_time_usecs=gt={start_time}"
        }
        return self.read(query=query)
