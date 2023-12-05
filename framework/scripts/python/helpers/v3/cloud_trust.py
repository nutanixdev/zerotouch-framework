from typing import Dict
from framework.helpers.rest_utils import RestAPIUtil
from ..pc_entity import PcEntity


class CloudTrust(PcEntity):
    kind = "cloud_trust"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/cloud_trusts"
        super(CloudTrust, self).__init__(session=session)

    @staticmethod
    def get_payload(cloud_type: str, remote_pc: str, remote_pc_username: str, remote_pc_password: str) -> Dict:
        spec = {
            "name": "",
            "description": "",
            "resources": {
                "cloud_type": cloud_type,
                "password": remote_pc_password,
                "url": remote_pc,
                "username": remote_pc_username
            }
        }

        payload = {
            "spec": spec
        }
        return payload
