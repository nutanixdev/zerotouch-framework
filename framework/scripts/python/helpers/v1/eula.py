import sys
from helpers.rest_utils import RestAPIUtil
from scripts.python.helpers.pe_entity_v1 import PeEntityV1
from helpers.log_utils import get_logger

logger = get_logger(__name__)


class Eula(PeEntityV1):
    """
    Class to accept End-User License Agreement (EULA)
    """

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/eulas"
        super(Eula, self).__init__(session=session)

    def is_eula_accepted(self):
        """
        This method check whether eula enabled or not.
        Returns:
            (boolean): True if EULA is accepted
                      False if eula is not accepted
        """
        response = self.read()
        for entity in response:
            if 'userDetailsList' in entity:
                return True
        return

    def accept_eula(self, username: str, company_name: str, job_title: str, cluster_info):
        """Accept End-User License Agreement (EULA)
        """
        endpoint = "accept"
        data = {
            "username": username,
            "companyName": company_name,
            "jobTitle": job_title
        }
        response = self.create(data=data, endpoint=endpoint)
        if response["value"]:
            logger.info(f"Accepted End-User License Agreement in {cluster_info}")
        else:
            raise Exception(f"Could not Accept End-User License Agreement in {cluster_info}. Error: {response}")
