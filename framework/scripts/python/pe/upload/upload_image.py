from typing import Dict
from framework.helpers.log_utils import get_logger
from framework.scripts.python.helpers.state_monitor.progress_monitor import TaskMonitor
from framework.scripts.python.helpers.v2.image import Image
from framework.scripts.python.pe.cluster_script import ClusterScript

logger = get_logger(__name__)


class UploadImagePe(ClusterScript):
    """
    The Script to Upload Image in PE clusters
    """

    def __init__(self, data: Dict, **kwargs):
        super(UploadImagePe, self).__init__(data, **kwargs)
        self.logger = self.logger or logger
        self.task_uuid_list = []

    def execute_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Only for parallel runs
        if self.parallel:
            self.set_current_thread_name(cluster_ip)

        pe_session = cluster_details["pe_session"]
        cluster_info = f"{cluster_ip}/ {cluster_details['cluster_info']['name']}" if (
            'name' in cluster_details['cluster_info']) else f"{cluster_ip}"

        try:
            if cluster_details.get("images"):
                image_op = Image(session=pe_session)
                image_name_list = [image["name"] for image in image_op.read()]

                for image_to_create in cluster_details["images"]:
                    try:
                        image_name = image_to_create['name']
                        if image_name in image_name_list:
                            self.logger.info(f"Image {image_name!r} already exists in {cluster_info!r}. Skipping...")
                            continue

                        self.logger.info(f"Uploading Image {image_name!r} in {cluster_info!r}")
                        image_payload, error = image_op.get_spec(image_to_create)
                        if error:
                            self.exceptions.append(f"Failed generating Upload Image spec for {image_name}: {error}")
                            continue
                        response = image_op.create(data=image_payload)

                        if response.get("task_uuid"):
                            self.logger.info(f"Submitted task {response['task_uuid']!r} for uploading of Image "
                                             f"{image_name!r}")
                            self.task_uuid_list.append(response["task_uuid"])
                        else:
                            self.exceptions.append(f"Could not upload the Image {image_name!r}. Error: {response}")
                    except Exception as e:
                        self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                               f"{cluster_info!r} with the error: {e}")

                # Monitor the tasks
                if self.task_uuid_list:
                    task_op = TaskMonitor(pe_session, task_uuid_list=self.task_uuid_list)
                    task_op.DEFAULT_CHECK_INTERVAL_IN_SEC = 30
                    task_op.DEFAULT_TIMEOUT_IN_SEC = 3600
                    app_response, status = task_op.monitor()
                    if app_response:
                        self.exceptions.append(f"Some tasks have failed. {app_response}")

                    if not status:
                        self.exceptions.append(f"Timed out. Uploading some or all Images in {cluster_info!r} "
                                               f"didn't happen in the prescribed timeframe")
            else:
                self.logger.info(f"No Images specified in {cluster_info!r} to upload. Skipping...")
        except Exception as e:
            self.exceptions.append(f"{type(self).__name__} failed for the cluster "
                                   f"{cluster_info!r} with the error: {e}")
            return

    def verify_single_cluster(self, cluster_ip: str, cluster_details: Dict):
        # Check if network is created in PE
        try:
            if not cluster_details.get("images"):
                return

            self.results["clusters"][cluster_ip] = {"Upload_Image": {}}
            pe_session = cluster_details["pe_session"]

            image_op = Image(pe_session)
            image_list = []

            for image in cluster_details.get("images"):
                # Set default status
                self.results["clusters"][cluster_ip]["Upload_Image"][image["name"]] = "CAN'T VERIFY"

                image_list = image_list or image_op.read()
                image_name_list = [image["name"] for image in image_list if image.get("name")]

                if image["name"] in image_name_list:
                    self.results["clusters"][cluster_ip]["Upload_Image"][image["name"]] = "PASS"
                else:
                    self.results["clusters"][cluster_ip]["Upload_Image"][image["name"]] = "FAIL"
        except Exception as e:
            self.logger.debug(e)
            self.logger.info(f"Exception occurred during the verification of {type(self).__name__!r} for {cluster_ip}")
