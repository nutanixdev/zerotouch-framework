from framework.helpers.rest_utils import RestAPIUtil
from .foundation_central import FoundationCentral

__metaclass__ = type


class FcApiKey(FoundationCentral):
    entity_type = "api_keys"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/api_keys"
        super(FcApiKey, self).__init__(session, self.resource_type)

    def generate_fc_api_key(self, alias: str):
        """Generate FC API Key

        Args:
            alias (str): Key name

        Returns:
            Response (dict): Return POST request response
            Example response:
            {
                'alias': 'api_key1',
                'api_key': 'eyJhbGciOI1NiIsIn.....Oqgqv-HWff4BAno3N_msHQgGpthF3BD2rMSg',
                'created_timestamp': '2023-10-10T11:42:12.000-07:00',
                'current_time': '0001-01-01T00:00:00.000Z',
                'key_uuid': 'b65ddbb9-10a0-411a-66a5-be7e5b8bd538'
            }
        """
        data = {"alias": alias}
        return self.create(data=data)
