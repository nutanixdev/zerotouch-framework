import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.objects.iam_proxy import IamProxyObjects
from framework.scripts.python.helpers.entity import Entity

class TestIamProxyObjects:
    @pytest.fixture
    def iam_proxy_objects(self):
        self.session =  MagicMock(spec=RestAPIUtil)
        return IamProxyObjects(session=self.session)

    def test_iam_proxy_objects_init(self, iam_proxy_objects):
        assert iam_proxy_objects.resource == "oss/iam_proxy" #Created in Entity Class
        assert iam_proxy_objects.session == self.session
        assert isinstance(iam_proxy_objects,IamProxyObjects)
        assert isinstance(iam_proxy_objects,Entity)
        

    def test_list_directory_services(self, mocker, iam_proxy_objects):
        mock_read = mocker.patch.object(IamProxyObjects,'read')
        mock_read.return_value = [{"name": "service1"}, {"name": "service2"}]

        response = iam_proxy_objects.list_directory_services()
        assert response == [{"name": "service1"}, {"name": "service2"}]

        mock_read.assert_called_once_with(endpoint="directory_services")

    def test_get_by_domain_name(self, mocker, iam_proxy_objects):
        mock_list_directory_services = mocker.patch.object(IamProxyObjects, 'list_directory_services')
        mock_list_directory_services.return_value = [
            {"spec": {"resources": {"domain_name": "domain1"}}},
            {"spec": {"resources": {"domain_name": "domain2"}}}
        ]

        response = iam_proxy_objects.get_by_domain_name("domain1")
        assert response == {"spec": {"resources": {"domain_name": "domain1"}}}
        mock_list_directory_services.assert_called_once()

        response = iam_proxy_objects.get_by_domain_name("domain3")
        assert response == []
        mock_list_directory_services.assert_called()

    def test_add_directory_service(self, mocker, iam_proxy_objects):
        mock_create = mocker.patch.object(IamProxyObjects,'create')
        mock_create.return_value = {"status": "success"}

        response = iam_proxy_objects.add_directory_service(
            ad_name="test_ad",
            ad_domain="domain.com",
            ad_directory_url="192.168.1.1",
            service_account_username="admin",
            service_account_password="password"
        )
        assert response == {"status": "success"}

        expected_payload = {
            "api_version": "3.1.0",
            "metadata": {"kind": "directory_service"},
            "spec": {
                "name": "test_ad",
                "resources": {
                    "domain_name": "domain.com",
                    "directory_type": "ACTIVE_DIRECTORY",
                    "url": "192.168.1.1",
                    "service_account": {
                        "username": "admin@domain.com",
                        "password": "password"
                    }
                }
            }
        }
        mock_create.assert_called_once_with(endpoint="directory_services", data=expected_payload)

    def test_create_ad_users(self, mocker, iam_proxy_objects):
        mock_create = mocker.patch.object(IamProxyObjects, 'create')
        mock_create.return_value = {"status": "success"}

        response = iam_proxy_objects.create_ad_users(
            idp_id="test_idp_id",
            usernames=["user1", "user2"]
        )
        assert response == {"status": "success"}

        expected_payload = {
            "users": [
                {
                    "type": "ldap",
                    "username": "user1",
                    "display_name": "user1",
                    "idp_id": "test_idp_id"
                },
                {
                    "type": "ldap",
                    "username": "user2",
                    "display_name": "user2",
                    "idp_id": "test_idp_id"
                }
            ]
        }
        mock_create.assert_called_once_with(data=expected_payload, endpoint="buckets_access_keys")

    def test_list_users(self, mocker, iam_proxy_objects):
        mock_read = mocker.patch.object(IamProxyObjects,'read')
        mock_read.return_value = {
            "length": 2,
            "total_matches": 2,
            "users": [{"name": "user1"}, {"name": "user2"}]
        }

        response = iam_proxy_objects.list_users()
        assert response == [{"name": "user1"}, {"name": "user2"}]

        mock_read.assert_called_once_with(endpoint="users")
