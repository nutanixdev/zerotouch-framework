from helpers.log_utils import get_logger
from scripts.python.helpers.karbon.karbon_clusters import KarbonCluster, KarbonClusterV1
from scripts.python.helpers.karbon.karbon_image import KarbonImage
from scripts.python.helpers.state_monitor.karbon_image_monitor import KarbonImageDownloadMonitor
from scripts.python.helpers.state_monitor.pc_task_monitor import PcTaskMonitor
from scripts.python.script import Script

logger = get_logger(__name__)


class CreateKarbonClusterPc(Script):
    """
    Class that creates NKE Clusters in PC
    """

    def __init__(self, data: dict, **kwargs):
        self.task_uuid_list = []
        self.response = None
        self.data = data
        self.pc_session = self.data["pc_session"]
        super(CreateKarbonClusterPc, self).__init__(**kwargs)
        self.logger = self.logger or logger

    def execute(self, **kwargs):
        pass
        try:
            if not self.data.get("nke_clusters"):
                self.logger.warning(f"Skipping NKE Clusters creation in '{self.data['pc_ip']}'")
                return

            karbon_cluster = KarbonCluster(self.pc_session)
            karbon_cluster_v1 = KarbonClusterV1(self.pc_session)
            existing_clusters_list = karbon_cluster.list()
            existing_clusters_name_list = [existing_cluster.get("cluster_metadata", {}).get("name")
                                           for existing_cluster in existing_clusters_list]

            image_op = KarbonImage(self.pc_session)
            available_images = image_op.list()
            available_images_version_list = {available_image.get("version"): available_image
                                             for available_image in available_images if available_image.get("version")}

            # First download the os_images in all nke_clusters
            images_to_download = []
            for cluster_to_create in self.data["nke_clusters"]:
                os_version = cluster_to_create.get("host_os")
                if os_version not in available_images_version_list:
                    continue

                image_obj = available_images_version_list[os_version]
                if image_obj.get("status") == KarbonImage.AVAILABLE and image_obj.get("uuid"):
                    images_to_download.append(image_obj["uuid"])

            for image_to_download in images_to_download:
                self.logger.info(f"Downloading the os-image '{image_to_download}'...")
                response = image_op.download(image_to_download)
                if not response.get("image_uuid"):
                    self.logger.error("Downloading image failed")
                    continue
                image_uuid = response["image_uuid"]
                response, status = KarbonImageDownloadMonitor(self.pc_session, image_uuid).monitor()

                if not status:
                    self.logger.error(f"Downloading image failed. {response}")
                self.logger.error(f"Downloaded the image successfully")

            for cluster_to_create in self.data["nke_clusters"]:
                name = cluster_to_create.get("name")

                cluster_exists = name in existing_clusters_name_list

                try:
                    # Category is already there, just need to add values to the category
                    if cluster_exists:
                        self.logger.warning(f"NKE cluster with name '{name}' already exists in {self.data['pc_ip']}!")
                        continue
                    else:

                        os_version = cluster_to_create.get("host_os")
                        if os_version not in available_images_version_list:
                            self.logger.warning(f"Specified '{os_version}' version is not available to download!")
                            continue

                        image_obj = available_images_version_list[os_version]
                        if image_obj.get("status") != KarbonImage.DOWNLOADED:
                            self.logger.error("Image doesn't exist!")

                        # create nke cluster
                        self.logger.info(f"Creating new NKE cluster '{name}'")
                        spec = karbon_cluster_v1.get_payload(cluster_to_create)
                        response = karbon_cluster_v1.create(data=spec, timeout=120)

                        if response.get("task_uuid"):
                            self.task_uuid_list.append(response.get("task_uuid"))

                        cluster_uuid = response.get("cluster_uuid")
                        self.logger.debug(cluster_uuid)
                except Exception as e:
                    self.exceptions.append(f"Failed to create NKE cluster {name}: {e}")

            if self.task_uuid_list:
                app_response, status = PcTaskMonitor(self.pc_session,
                                                     task_uuid_list=self.task_uuid_list).monitor()

                if app_response:
                    self.exceptions.append(f"Some tasks have failed. {app_response}")

                if not status:
                    self.exceptions.append(
                        "Timed out. Creating NKE Clusters in PC didn't happen in the prescribed timeframe")
        except Exception as e:
            self.exceptions.append(e)

    def verify(self, **kwargs):
        if not self.data.get("nke_clusters"):
            return

        # Initial status
        self.results["NKE_Clusters"] = {}

        karbon_cluster = KarbonCluster(self.pc_session)
        existing_clusters_list = []
        existing_cluster_detail_list = {}

        for cluster_to_create in self.data["nke_clusters"]:
            name = cluster_to_create.get("name")

            # Initial status
            self.results["NKE_Clusters"][name] = "CAN'T VERIFY"

            existing_clusters_list = existing_clusters_list or karbon_cluster.list()
            existing_cluster_detail_list = existing_cluster_detail_list or {
                                               existing_cluster["cluster_metadata"]["name"]: existing_cluster
                                               for existing_cluster in existing_clusters_list
                                               if existing_cluster.get("cluster_metadata", {}).get("name")
                                           }
            if name in existing_cluster_detail_list:
                if existing_cluster_detail_list[name].get("task_progress_message") == "Kubernetes Cluster deployment " \
                                                                                      "successful":
                    self.results["NKE_Clusters"][name] = "PASS"
                else:
                    self.results["NKE_Clusters"][name] = "FAIL"
            else:
                self.results["NKE_Clusters"] = {name: "FAIL"}