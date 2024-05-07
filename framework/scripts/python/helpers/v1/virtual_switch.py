from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class VirtualSwitch(PeEntityV1):
    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/networking/v2.a1/dvs/virtual-switches"
        self.cluster_info = {}
        super(VirtualSwitch, self).__init__(session=session)

    def get_vs_uuid(self, name: str):
        """Get virtual switch uuid

        Args:
            name (str): Virtual switch name

        Returns:
            str: Virtual switch uuid
        """
        response = self.read()
        vs_uuid = None
        for vs in response:
            if vs['data']['name'] == name:
                vs_uuid = vs["data"]["extId"]
        if not vs_uuid:
            raise Exception(f"Could not fetch the UUID of the entity {type(self).__name__} with name {name}")
        return vs_uuid
