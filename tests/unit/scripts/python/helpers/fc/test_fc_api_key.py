import pytest
from framework.scripts.python.helpers.fc.fc_api_key import FcApiKey
from framework.scripts.python.helpers.fc_entity import FcEntity

class TestFcApiKey:
    @pytest.fixture
    def fc_api_key(self, mocker):
        self.mock_session = mocker.MagicMock()
        return FcApiKey(session=self.mock_session)
    
    def test_fc_api_key_init(self, fc_api_key):
        assert fc_api_key.session == self.mock_session
        assert fc_api_key.resource_type == "/api_keys"
        assert isinstance(fc_api_key, FcApiKey)
        
    def test_generate_fc_api_key(self, mocker, fc_api_key):
        mock_create = mocker.patch.object(FcEntity, "create")
        alias = "test_alias"
        data = {"alias": alias}
        mock_create.return_value = {"alias": alias, "api_key": "test_api"}
        response = fc_api_key.generate_fc_api_key(alias)
        mock_create.assert_called_once_with(data=data)
        assert response == {"alias": alias, "api_key": "test_api"}
