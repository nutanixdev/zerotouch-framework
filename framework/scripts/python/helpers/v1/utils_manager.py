from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class UtilsManager(PeEntityV1):
    """
    Class to change the default system password
    """
    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/utils"
        super(UtilsManager, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def change_default_system_password(self, old_password, new_password) -> Dict:
        endpoint = "change_default_system_password"
        data = {
            "oldPassword":  old_password,
            "newPassword": new_password
        }
        return self.create(data=data, endpoint=endpoint)
