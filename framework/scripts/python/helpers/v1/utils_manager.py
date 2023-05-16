from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class UtilsManager(PeEntityV1):
    """
    Class to change the default system password
    """
    DEFAULT_SYSTEM_PASSWORD = "Nutanix/4u"
    DEFAULT_USERNAME = "admin"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/utils"
        super(UtilsManager, self).__init__(session=session)

    def change_default_system_password(self, new_password, cluster_info: str):
        endpoint = "change_default_system_password"
        data = {
            "oldPassword":  self.DEFAULT_SYSTEM_PASSWORD,
            "newPassword": new_password
        }
        response = self.create(data=data, endpoint=endpoint, timeout=120)
        if response["value"]:
            logger.info(f"Default System password updated with new password in {cluster_info}")
        else:
            raise Exception(f"Could not change the system password in {cluster_info}. Error: {response}")
