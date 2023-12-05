from typing import List, Dict
from framework.helpers.rest_utils import RestAPIUtil
from .karbon import Karbon


class KarbonImage(Karbon):
    """
    Class the handle the /karbon/acs/image API calls
    """
    kind = "acs/image"
    DOWNLOADED = "Downloaded"
    COMPLETE = "COMPLETE"
    AVAILABLE = "Available"

    def __init__(self, session: RestAPIUtil):
        self.session = session
        self.resource_type = "/acs/image"
        super(KarbonImage, self).__init__(session=session, resource_type=self.resource_type)

    def list(self, **kwargs) -> List:
        endpoint = "list"
        return super(KarbonImage, self).read(endpoint=endpoint)

    def download(self, uuid: str) -> Dict:
        """
        Download image with uuid
        Args:
          uuid(str): The uuid of the image
        Returns:
          dict, the api response
        """
        endpoint = "download"
        payload = {"uuid": uuid}
        return self.create(endpoint=endpoint, data=payload)

    def get_image_status(self, image_uuid: str):
        """
        Get UUID status of the karbon image
        Args:
          image_uuid(str): uuid of the karbon image
        Returns:
          dict: The api response, example:
          {"image_description": "Karbon node OS version 1.1",
          "os_flavor": "centos7.5.1804", "status": "COMPLETE",
          "version": "ntnx-1.1"}
        """
        endpoint = f"download/{image_uuid}"
        return self.read(endpoint=endpoint)
