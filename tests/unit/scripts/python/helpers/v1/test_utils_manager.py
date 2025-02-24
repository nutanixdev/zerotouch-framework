import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.utils_manager import UtilsManager
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestUtilsManager:
    @pytest.fixture
    def utils_manager(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return UtilsManager(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_utils_manager_init(self, utils_manager):
        assert utils_manager.resource_type == "/utils"
        assert utils_manager.session == self.session
        assert utils_manager.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(utils_manager, UtilsManager)
        assert isinstance(utils_manager, PeEntityV1)
    
    def test_change_default_system_password(self, mocker, utils_manager):
        old_password = "old_password"
        new_password = "new_password"
        data = {"oldPassword": old_password, "newPassword": new_password}
        
        mock_create = mocker.patch.object(PeEntityV1, "create")
        utils_manager.change_default_system_password(old_password=old_password, new_password=new_password)
        mock_create.assert_called_once_with(data=data, endpoint="change_default_system_password")
