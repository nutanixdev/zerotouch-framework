from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class UtilsManager(PeEntityV1):
    """
    Class to change the default system password
    """
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"
    DEFAULT_USERNAME = "admin"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/utils"
        super(UtilsManager, self).__init__(session=session)

    def change_default_system_password(self, new_password) -> Dict:
        endpoint = "change_default_system_password"
        data = {
            "oldPassword":  self.DEFAULT_SYSTEM_PASSWORD,
            "newPassword": new_password
        }
        return self.create(data=data, endpoint=endpoint)
