import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from framework.scripts.python.helpers.v1.authentication import AuthN
from unittest.mock import MagicMock

class TestAuthentication:
    @pytest.fixture
    def authn(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return AuthN(self.session, self.proxy_cluster_uuid)
    
    def test_authn_init(self, authn):
        '''
        Test that the AuthN class is an instance of PeEntityV1 and
        that the session attribute is set correctly
        '''
        assert authn.resource_type == "/authconfig"
        assert authn.session == self.session
        assert authn.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(authn, AuthN)
        assert isinstance(authn, PeEntityV1)

    def test_create_directory_services(self, authn, mocker):
        ad_params = {
            "ad_name": "Test AD",
            "ad_domain": "test.domain",
            "ad_directory_url": "ldap://test.domain",
            "directory_type": "Active Directory",
            "service_account_username": "admin",
            "service_account_password": "password"
        }
        expected_spec = {
            "name": ad_params["ad_name"],
            "domain": ad_params["ad_domain"],
            "directoryUrl": ad_params["ad_directory_url"],
            "groupSearchType": "NON_RECURSIVE",
            "directoryType": ad_params["directory_type"],
            "connectionType": "LDAP",
            "serviceAccountUsername": ad_params["service_account_username"],
            "serviceAccountPassword": ad_params["service_account_password"]
        }
        mock_create = mocker.patch.object(PeEntityV1, "create")
        authn.create_directory_services(**ad_params)
        mock_create.assert_called_once_with(data=expected_spec, endpoint="directories") 
        
        
    def test_get_directories(self, authn, mocker):
        mock_read = mocker.patch.object(PeEntityV1, "read")
        authn.get_directories()
        mock_read.assert_called_once_with(endpoint="directories")

    def test_delete_directory_services(self, authn, mocker):
        name = "Test AD"
        mock_delete = mocker.patch.object(PeEntityV1, "delete")
        authn.delete_directory_services(name)
        mock_delete.assert_called_once_with(endpoint=f"directories/{name}")

    def test_get_role_mappings(self, authn, mocker):
        directory_name = "Test AD"
        mock_read = mocker.patch.object(PeEntityV1, "read")
        authn.get_role_mappings(directory_name)
        mock_read.assert_called_once_with(endpoint=f"directories/{directory_name}/role_mappings")

    def test_create_role_mapping(self, authn, mocker):
        directory_name = "Test AD"
        role_mapping = {
            "role_type": "admin",
            "entity_type": "user",
            "values": ["user1", "user2"]
        }
        mock_create = mocker.patch.object(PeEntityV1, "create")
        authn.create_role_mapping(directory_name, role_mapping)
        mock_create.assert_called_once_with(data={
            "directoryName": directory_name,
            "role": role_mapping["role_type"],
            "entityType": role_mapping["entity_type"],
            "entityValues": role_mapping["values"]
        }, endpoint=f"directories/{directory_name}/role_mappings")
        

    def test_delete_role_mapping(self, authn, mocker):
        directory_name = "Test AD"
        role_mapping = {
            "role_type": "admin",
            "entity_type": "user"
        }
        mock_delete = mocker.patch.object(PeEntityV1, "delete")
        authn.delete_role_mapping(role_mapping, directory_name)
        mock_delete.assert_called_once_with(query={
            "role": role_mapping["role_type"],
            "entityType": role_mapping["entity_type"]
        }, endpoint=f"directories/{directory_name}/role_mappings")