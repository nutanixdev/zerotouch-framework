from typing import List
from framework.helpers.log_utils import get_logger
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity import PcEntity
from ..v3.cluster import Cluster as PcCluster

logger = get_logger(__name__)


class Ova(PcEntity):
    kind = "ova"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/ovas"
        self.session = session
        super(Ova, self).__init__(session=session)

    def url_upload(self, ova_config_list: List):
        """
        Upload OVAs with URL to PC cluster(s)

        Args:
            ova_config_list (list): OVA details which contain below information
                url (str): URL to upload. e.g: "http(s)://where-the-file-is-present"
                name (str): Name of the file to upload
                cluster_name_list (list): Cluster name list
                ova_config_list = [
                        {
                            url:'http://where-the-file-is-present',
                            name:'ova-name',
                            cluster_name_list: ['cluster1', 'cluster2']
                        }
                    ]

        Returns:
            list: list of task uuids
        """
        requests = []
        pc_cluster = PcCluster(self.session)
        pc_cluster.get_pe_info_list()
        for ova_cofig in ova_config_list:
            cluster_uuid_mappings = [{'kind': 'cluster', 'uuid': pc_cluster.name_uuid_map.get(cluster_name)}
                                     for cluster_name in ova_cofig["cluster_name_list"]]
            payload = {
                    "url": ova_cofig["url"],
                    "name": ova_cofig["name"],
                    "upload_cluster_ref_list": cluster_uuid_mappings
                }
            requests.append(payload)
        return self.batch_op.batch_create(request_payload_list=requests)

    def get_vm_spec_from_ova_uuid(self, ova_uuid):
        """
        Get vm creation spec from OVA
        Args:
            ova_uuid(list): OVA uuid to get vm spec from
        Returns:
            vm_config_spec_list(list): a list of vm spec to be deployed
        """
        response = self.read(uuid=ova_uuid, endpoint="vm_spec")
        if response:
            return response["vm_spec"]["spec"]

    def get_ova_by_cluster_reference(self, ova_name: str, cluster_name: str = None, cluster_uuid: str = None):
        entities = self.list(filter=f"name=={ova_name}")
        if not cluster_uuid:
            pc_cluster = PcCluster(self.session)
            pc_cluster.get_pe_info_list()
            cluster_uuid = pc_cluster.name_uuid_map.get(cluster_name)
        for entity in entities:
            cluster_uuids = [cluster["uuid"] for cluster in
                              entity["info"]["current_cluster_reference_list"]]
            if cluster_uuid in cluster_uuids:
                return entity
        return None
