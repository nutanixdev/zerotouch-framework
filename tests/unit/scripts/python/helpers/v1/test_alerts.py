import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.alert import Alert
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1


class TestAlert:
    @pytest.fixture
    def alert(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Alert(session=self.session)
    
    def test_alert_init(self, alert):
        '''
        Test that the Alert class is an instance of PeEntityV1 and
        that the session attribute is set correctly
        '''
        assert alert.resource_type == "/alerts"
        assert alert.session == self.session
        assert isinstance(alert, Alert)
        assert isinstance(alert, PeEntityV1)
        
    def test_get_payload(self):
        payload = Alert.get_payload()
        expected_payload = {
            "enable": True,
            "enableEmailDigest": True,
            "enableDefaultNutanixEmail": True,
            "defaultNutanixEmail": None,
            "emailContactList": None,
            "tunnelDetails": None,
            "emailConfigRules": None,
            "emailTemplate": None,
            "skipEmptyAlertEmailDigest": None,
            "alertEmailDigestSendTime": None,
            "alertEmailDigestSendTimezone": None
        }
        assert payload == expected_payload


    def test_create(self, alert, mocker):
        endpoint = "/alert_endpoint"
        payload = {
            "enable": True,
            "enableEmailDigest": True,
            "enableDefaultNutanixEmail": True,
            "defaultNutanixEmail": None,
            "emailContactList": None,
            "tunnelDetails": None,
            "emailConfigRules": None,
            "emailTemplate": None,
            "skipEmptyAlertEmailDigest": None,
            "alertEmailDigestSendTime": None,
            "alertEmailDigestSendTimezone": None
        }
        mock_create = mocker.patch.object(PeEntityV1, "create")
        alert.create(endpoint=endpoint)
        mock_create.assert_called_once_with(endpoint=endpoint, data=payload)

    def test_update(self, alert, mocker):
        endpoint = "/alerts"
        payload = {
            "enable": True,
            "enableEmailDigest": True,
            "enableDefaultNutanixEmail": True,
            "defaultNutanixEmail": None,
            "emailContactList": None,
            "tunnelDetails": None,
            "emailConfigRules": None,
            "emailTemplate": None,
            "skipEmptyAlertEmailDigest": None,
            "alertEmailDigestSendTime": None,
            "alertEmailDigestSendTimezone": None
        }
        mock_update = mocker.patch.object(PeEntityV1, "update")
        alert.update(endpoint=endpoint)
        mock_update.assert_called_once_with(endpoint=endpoint, data=payload)


