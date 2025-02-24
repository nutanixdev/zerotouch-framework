from typing import List
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity_v3 import PcEntity
from ..v3.cluster import Cluster as PcCluster

logger = get_logger(__name__)


class Image(PcEntity):
    kind = "image"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/images"
        self.session = session
        super(Image, self).__init__(session=session)

    def url_upload(self, image_config_list: List) -> List:
        """
        Upload new image(s) with url to PC cluster(s)

        Args:
            image_config_list (list): List of image configs
            image_config_list = [
                            {
                                'name': 'image_name',
                                'description': '',
                                'image_type': 'DISK_IMAGE' or 'ISO_IMAGE',
                                'url': 'http://where-the-file-is-present',
                                'cluster_name_list': ['cluster-name1', 'cluster-name2']
                            }
                        ]
        """
        payload_list = []
        pc_cluster = PcCluster(self.session)
        pc_cluster.get_pe_info_list()
        for image_config in image_config_list:
            cluster_uuid_mappings = [{'kind': 'cluster', 'uuid': pc_cluster.name_uuid_map.get(cluster_name)}
                                     for cluster_name in image_config["cluster_name_list"]]
            payload = {
                    "spec": {
                        "name": image_config["name"],
                        "description": image_config.get("description", ""),
                        "resources": {
                            "image_type": image_config["image_type"],
                            "source_uri": image_config["url"],
                            "initial_placement_ref_list": cluster_uuid_mappings
                        }
                    },
                    "metadata": {
                        "kind": "image"
                    }
                }
            payload_list.append(payload)
        return self.batch_op.batch_create(request_payload_list=payload_list)
