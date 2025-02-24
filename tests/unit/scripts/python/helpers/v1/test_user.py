import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.user import User
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestUser:
    @pytest.fixture
    def user(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return User(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_user_init(self, user):
        assert user.resource_type == "/users"
        assert user.session == self.session
        assert user.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(user, User)
        assert isinstance(user, PeEntityV1)
        
    def test_get_payload(self, user):
        user_name = "test_user"
        user_password = "test_password"
        first_name = "test_first_name"
        last_name = "test_last_name"
        
        expected_payload = {
            'profile': {
                'username': user_name,
                'password': user_password,
                'first_name': first_name,
                'last_name': last_name
            }
        }
        
        assert user.get_payload(user_name, user_password, first_name, last_name) == expected_payload
        
    def test_create_new_role(self, mocker, user):
        user_name = "test_user"
        role_list = ["test_role"]
        endpoint = f"{user_name}/roles"
        
        mock_create = mocker.patch.object(PeEntityV1, "create")
        user.create_new_role(user_name, role_list)
        mock_create.assert_called_once_with(data=role_list, endpoint=endpoint)
        
    def test_create_user(self, mocker, user):
        user_name = "test_user"
        user_password = "test_password"
        first_name = "test_first_name"
        last_name = "test_last_name"
        
        payload = user.get_payload(user_name, user_password, first_name, last_name)
        
        mock_create = mocker.patch.object(PeEntityV1, "create")
        user.create_user(user_name, user_password, first_name, last_name)
        mock_create.assert_called_once_with(data=payload)
        
    def test_update(self, mocker, user):
        user_name = "test_user"
        user_password = "test_password"
        first_name = "test_first_name"
        last_name = "test_last_name"
        
        payload = user.get_payload(user_name, user_password, first_name, last_name)
        
        mock_update = mocker.patch.object(PeEntityV1, "update")
        user.update(user_name=user_name, user_password=user_password, first_name=first_name, last_name=last_name)
        mock_update.assert_called_once_with(data=payload)        