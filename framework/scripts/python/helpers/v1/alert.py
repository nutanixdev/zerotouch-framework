from framework.helpers.rest_utils import RestAPIUtil
from ..pe_entity_v1 import PeEntityV1


class Alert(PeEntityV1):
    """
    Class to create/update/delete/read alert
    """

    def __init__(self, session: RestAPIUtil, proxy_cluster_uuid=None):
        self.resource_type = "/alerts"
        super(Alert, self).__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    @staticmethod
    def get_payload(payload_type="configuration", **kwargs):
        if payload_type == "configuration":
            return {
                "enable": kwargs.pop('enable', True),
                "enableEmailDigest": kwargs.pop('enableEmailDigest', True),
                "enableDefaultNutanixEmail": kwargs.pop('enableDefaultNutanixEmail', True),
                "defaultNutanixEmail": kwargs.pop('defaultNutanixEmail', None),
                "emailContactList": kwargs.pop('emailContactList', None),
                "tunnelDetails": kwargs.pop('tunnelDetails', None),
                "emailConfigRules": kwargs.pop('emailConfigRules', None),
                "emailTemplate": kwargs.pop('emailTemplate', None),
                "skipEmptyAlertEmailDigest": kwargs.pop('skipEmptyAlertEmailDigest', None),
                "alertEmailDigestSendTime": kwargs.pop('alertEmailDigestSendTime', None),
                "alertEmailDigestSendTimezone": kwargs.pop('alertEmailDigestSendTimezone', None)
            }
        return {}

    def create(self, endpoint=None, **kwargs) -> dict:
        return super().create(data=self.get_payload(**kwargs), endpoint=endpoint)

    def update(self, endpoint=None, **kwargs):
        super().update(data=self.get_payload(**kwargs), endpoint=endpoint)
