from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pc_entity import PcEntity
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Cluster(PcEntity):
    kind = "cluster"

    def __init__(self, session: RestAPIUtil):
        self.uuid_ip_map = {}
        self.name_uuid_map = {}
        self.resource_type = "/clusters"
        super(Cluster, self).__init__(session=session)

    def get_pe_info_list(self):
        """
        Set name: uuid and ip: name mapping for all the registered clusters
        """
        clusters = self.list()

        for cluster in clusters:
            if "PRISM_CENTRAL" in cluster["status"]["resources"]["config"]["service_list"]:
                continue
            ip = cluster["status"]["resources"]["network"].get("external_ip", None)
            if cluster.get("spec", {}).get("name"):
                name = cluster["spec"]["name"]
            elif cluster.get("status", {}).get("name"):
                name = cluster["status"]["name"]
            else:
                continue
            uuid = cluster.get("metadata", {}).get("uuid")
            self.name_uuid_map[name] = uuid
            self.uuid_ip_map[uuid] = ip

        return
