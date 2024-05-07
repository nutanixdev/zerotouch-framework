from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Snmp(PeEntityV1):
    """
    Class to create/update/delete/read Snmp users/ traps
    """

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/snmp"
        super(Snmp, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    @staticmethod
    def get_payload(payload_type="users", **kwargs):
        if payload_type == "users":
            return {
                "authKey": kwargs.pop('authKey', None),
                "authType": kwargs.pop('authType', None),
                "privKey": kwargs.pop('privKey', None),
                "privType": kwargs.pop('privType', None),
                "username": kwargs.pop('username', None)
            }
        elif payload_type == "traps":
            return {
                "communityString": kwargs.pop('communityString', None),
                "engineId": kwargs.pop('engineId', None),
                "inform": kwargs.pop('inform', None),
                "port": kwargs.pop('port', None),
                "receiverName": kwargs.pop('receiverName', None),
                "transportProtocol": kwargs.pop('transportProtocol', None),
                "trapAddress": kwargs.pop('trapAddress', None),
                "trapUsername": kwargs.pop('trapUsername', None),
                "version": kwargs.pop('version', None)
            }
        else:
            return {}

    def create_user(self, endpoint="users", **kwargs) -> dict:
        return super().create(data=self.get_payload(payload_type="users", **kwargs), endpoint=endpoint)

    def update_user(self, endpoint="users", **kwargs):
        return super().update(data=self.get_payload(payload_type="users", **kwargs, endpoint=endpoint))

    def delete_user(self, name: str) -> dict:
        return super().delete(endpoint=f"users/{name}")

    def create_trap(self, endpoint="traps", **kwargs) -> dict:
        return super().create(data=self.get_payload(payload_type="traps", **kwargs), endpoint=endpoint)

    def update_trap(self, endpoint="traps", **kwargs):
        return super().update(data=self.get_payload(payload_type="traps", **kwargs, endpoint=endpoint))

    def delete_trap(self, name: str) -> dict:
        return super().delete(endpoint=f"traps/{name}")
