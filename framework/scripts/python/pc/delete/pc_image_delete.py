from typing import Dict

from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.v3.image import Image
from framework.scripts.python.script import Script
from framework.scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor

logger = get_logger(__name__)


class PcImageDelete(Script):
    """
    Class to delete images from PC
    """

    def __init__(self, data: Dict, **kwargs):
        self.data = data
        self.pc_session = data["pc_session"]
        super(PcImageDelete, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self):
        try:
            if self.data.get('images'):
                image_config_list = self.data.get('images')
                image_delete = Image(session=self.pc_session)

                # Get Exisiting image list from PC
                existing_image_uuid_map = {
                    image.get('status', {}).get('name'): image.get('metadata',{}).get('uuid')
                    for image in image_delete.list()
                }
                images_to_delete_uuid_list = []
                # Check if Image exists in PC
                for image_config in image_config_list:
                    if image_config['name'] not in existing_image_uuid_map.keys():
                        logger.warning(f"Image {image_config['name']} doesn't exist")
                    else:
                        images_to_delete_uuid_list.append(existing_image_uuid_map[image_config['name']])

                # Delete images to PC clusters
                if not images_to_delete_uuid_list:
                    self.logger.warning(f"Provided Images are not present in {self.data['pc_ip']}")
                    return
                logger.info(f"Trigger batch delete API for Images in {self.data['pc_ip']!r}")
                task_uuid_list = image_delete.batch_op.batch_delete(images_to_delete_uuid_list)

                #Monitor Tasks
                if task_uuid_list:
                    app_response, status = PcTaskMonitor(
                        self.pc_session,
                        task_uuid_list=task_uuid_list
                    ).monitor()

                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append("Timed out. Image delete didn't happen in the prescribed timeframe")

        except Exception as e:
            self.exceptions.append(e)

    def verify(self):
        """
        Verify if the images are deleted in PC
        """
        if not self.data.get("images"):
            return
        try:
            self.results["Image_Delete"] = {}
            image_upload = Image(session=self.pc_session)

            # Get Exisiting image list from PC
            existing_image_list = [image.get('status', {}).get('name') for image in image_upload.list()]

            # Check if the image(s) are deleted in PC
            for image_config in self.data.get("images"):
                if image_config["name"] not in existing_image_list:
                    self.results["Image_Delete"][image_config["name"]] = "PASS"
                else:
                    self.results["Image_Delete"][image_config["name"]] = "FAIL"
        except Exception as e:
            self.logger.error(e)
