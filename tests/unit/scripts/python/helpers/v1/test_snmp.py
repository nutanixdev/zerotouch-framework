import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.snmp import Snmp
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestSnmp:
    @pytest.fixture
    def snmp(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return Snmp(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)

    def test_snmp_init(self, snmp):
        assert snmp.resource_type == "/snmp"
        assert snmp.session == self.session
        assert snmp.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(snmp, Snmp)
        assert isinstance(snmp, PeEntityV1)
        
    def test_get_payload_users(self, snmp):
        payload = snmp.get_payload(
            payload_type="users", authKey="test_authKey",
            authType="test_authType", privKey="test_privKey",
            privType="test_privType", username="test_username"
            )
        assert payload == {
            "authKey": "test_authKey",
            "authType": "test_authType",
            "privKey": "test_privKey",
            "privType": "test_privType",
            "username": "test_username"
        }

    def test_get_payload_traps(self, snmp):
        payload = snmp.get_payload(
            payload_type="traps", communityString="test_communityString",
            engineId="test_engineId", inform="test_inform",
            port="test_port", receiverName="test_receiverName",
            transportProtocol="test_transportProtocol", trapAddress="test_trapAddress",
            trapUsername="test_trapUsername", version="test_version"
            )
        assert payload == {
            "communityString": "test_communityString",
            "engineId": "test_engineId",
            "inform": "test_inform",
            "port": "test_port",
            "receiverName": "test_receiverName",
            "transportProtocol": "test_transportProtocol",
            "trapAddress": "test_trapAddress",
            "trapUsername": "test_trapUsername",
            "version": "test_version"
        }
    
    def test_create_user(self, mocker,snmp):
        user_data = {
            "authKey": "test_authKey",
            "authType": "test_authType",
            "privKey": "test_privKey",
            "privType": "test_privType",
            "username": "test_username"
        }
        mock_create = mocker.patch.object(
            PeEntityV1, "create", return_value={"status": "success"})
        response = snmp.create_user(**user_data)
        mock_create.assert_called_once_with(data=user_data, endpoint="users")
        assert response == {"status": "success"}

    def test_update_user(self, mocker, snmp):
        user_data = {
            "authKey": "test_authKey",
            "authType": "test_authType",
            "privKey": "test_privKey",
            "privType": "test_privType",
            "username": "test_username"
        }
        mock_update = mocker.patch.object(
            PeEntityV1, "update", return_value={"status": "success"})
        response = snmp.update_user(**user_data)
        mock_update.assert_called_once_with(data=user_data)
        assert response == {"status": "success"}

    def test_delete_user(self, mocker, snmp):
        username = "test_username"
        mock_delete = mocker.patch.object(
            PeEntityV1, "delete", return_value={"status": "success"})
        response = snmp.delete_user(username)
        mock_delete.assert_called_once_with(endpoint=f"users/{username}")
        assert response == {"status": "success"}

    def test_create_trap(self, mocker, snmp):
        trap_data = {
            "communityString": "test_communityString",
            "engineId": "test_engineId",
            "inform": "test_inform",
            "port": "test_port",
            "receiverName": "test_receiverName",
            "transportProtocol": "test_transportProtocol",
            "trapAddress": "test_trapAddress",
            "trapUsername": "test_trapUsername",
            "version": "test_version"
        }
        mock_create = mocker.patch.object(
            PeEntityV1, "create", return_value={"status": "success"})
        response = snmp.create_trap(**trap_data)
        mock_create.assert_called_once_with(data=trap_data, endpoint="traps")
        assert response == {"status": "success"}

    def test_update_trap(self, mocker, snmp):
        trap_data = {
            "communityString": "test_communityString",
            "engineId": "test_engineId",
            "inform": "test_inform",
            "port": "test_port",
            "receiverName": "test_receiverName",
            "transportProtocol": "test_transportProtocol",
            "trapAddress": "test_trapAddress",
            "trapUsername": "test_trapUsername",
            "version": "test_version"
        }
        mock_update = mocker.patch.object(
            PeEntityV1, "update", return_value={"status": "success"})
        response = snmp.update_trap(**trap_data)
        mock_update.assert_called_once_with(data=trap_data)
        assert response == {"status": "success"}

    def test_delete_trap(self, mocker, snmp):
        trap_name = "test_trapName"
        mock_delete = mocker.patch.object(
            PeEntityV1, "delete", return_value={"status": "success"})   
        response = snmp.delete_trap(trap_name)
        mock_delete.assert_called_once_with(endpoint=f"traps/{trap_name}")
        assert response == {"status": "success"}            
