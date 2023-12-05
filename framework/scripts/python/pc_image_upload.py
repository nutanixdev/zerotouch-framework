from typing import Dict

from framework.helpers.log_utils import get_logger
from .helpers.v3.image import Image
from .script import Script
from .helpers.state_monitor.pc_task_monitor import PcTaskMonitor

logger = get_logger(__name__)


class PcImageUpload(Script):
    """
    Class to upload images to PC clusters
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = data["pc_session"]
        super(PcImageUpload, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        try:
            if self.data.get("images"):
                image_config_list = self.data.get("images")
                image_upload = Image(session=self.pc_session)

                # Get Exisiting image list from PC
                existing_image_list = [image.get('status', {}).get('name') for image in image_upload.list()]

                # Check if Image already exists in PC & remove the config from config list
                for image_config in image_config_list:
                    if image_config["name"] in existing_image_list:
                        image_config_list.remove(image_config)
                        logger.warning(f"Image {image_config['name']} already exists")

                # Upload images to PC clusters
                task_uuid_list = image_upload.url_upload(image_config_list)
                if task_uuid_list:
                    app_response, status = PcTaskMonitor(self.pc_session,
                                                        task_uuid_list=task_uuid_list).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append("Timed out. Image upload didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        """
        Verify if the images are present in PC
        """
        if not self.data.get("images"):
            return
        try:
            self.results["Image_Upload"] = {}
            image_upload = Image(session=self.pc_session)

            # Get Exisiting image list from PC
            existing_image_list = [image.get('status', {}).get('name') for image in image_upload.list()]

            # Check if the image(s) are present in PC
            for image_config in self.data.get("images"):
                if image_config["name"] in existing_image_list:
                    self.results["Image_Upload"][image_config["name"]] = "PASS"
                else:
                    self.results["Image_Upload"][image_config["name"]] = "FAIL"
        except Exception as e:
            self.logger.error(e)
