import pytest
from framework.scripts.python.helpers.v4.security_rule import SecurityPolicy
from unittest.mock import MagicMock
from framework.helpers.v4_api_client import ApiClientV4
import ntnx_microseg_py_client.models.microseg.v4.config as v4MicrosegConfig

class TestSecurityPolicy:
    @pytest.fixture
    def security_policy(self):
        return SecurityPolicy()
    
    def test_security_rule_init(self, security_policy):
        assert security_policy.resource_type == "microseg/v4.0.b1/config/policies"
        assert security_policy.kind == "SecurityPolicy"
        

    def test_list(self, security_policy):
        security_policy.network_security_policies_api.list_network_security_policies = MagicMock(return_value=MagicMock(data=[]))
        result = security_policy.list()
        assert result.data == []
        security_policy.network_security_policies_api.list_network_security_policies.assert_called_once()

    def test_get_name_list(self, security_policy):
        mock_data = MagicMock(data=[MagicMock(), MagicMock()])
        mock_data.data[0].name = "policy1"
        mock_data.data[1].name = "policy2"
        security_policy.list = MagicMock(return_value=mock_data)
        result = security_policy.get_name_list()
        assert result == ["policy1", "policy2"]

    def test_get_name_uuid_dict(self, security_policy):
        mock_data = MagicMock(data=[MagicMock(), MagicMock()])
        mock_data.data[0].name = "policy1"
        mock_data.data[0].ext_id = "uuid1"
        mock_data.data[1].name = "policy2"
        mock_data.data[1].ext_id = "uuid2"
        security_policy.list = MagicMock(return_value=mock_data)
        result = security_policy.get_name_uuid_dict()
        assert result == {"policy1": "uuid1", "policy2": "uuid2"}

    def test_get_by_ext_id(self, security_policy):
        mock_policy = MagicMock()
        security_policy.network_security_policies_api.get_network_security_policy_by_id = MagicMock(return_value=mock_policy)
        result = security_policy.get_by_ext_id("uuid1")
        assert result == mock_policy
        security_policy.network_security_policies_api.get_network_security_policy_by_id.assert_called_once_with("uuid1")

    def test_create_security_policy_spec(self, security_policy):
        sp_info = {
            "name": "test_policy",
            "type": "APPLICATION",
            "description": "Test policy description",
            "allow_ipv6_traffic": True,
            "hitlog": True,
            "policy_mode": "MONITOR",
            "app_rule": [],
            "two_env_isolation_rule": []
        }
        result = security_policy.create_security_policy_spec(sp_info)
        assert result.name == "test_policy"
        assert result.type == v4MicrosegConfig.SecurityPolicyType.SecurityPolicyType.APPLICATION
        assert result.description == "Test policy description"
        assert result.allow_ipv6_traffic == True
        assert result.isHitlogEnabled == True
        assert result.state == v4MicrosegConfig.SecurityPolicyState.SecurityPolicyState.MONITOR
        assert result.rules == []

    def test_update_security_policy_spec(self, security_policy):
        sp_info = {
            "new_name": "updated_policy",
            "description": "Updated policy description",
            "allow_ipv6_traffic": True,
            "hitlog": True,
            "policy_mode": "MONITOR",
            "app_rule": ["dummy_rule"],
        }
        sp_obj = MagicMock()
        security_policy.add_rule = MagicMock(return_value=None)
        ApiClientV4.get_api_client = MagicMock(return_value=MagicMock(get_etag=MagicMock(return_value="etag")))
        result, etag = security_policy.update_security_policy_spec(sp_info, sp_obj)

        assert result.name == "updated_policy"
        assert result.description == "Updated policy description"
        assert result.allow_ipv6_traffic == True
        assert result.isHitlogEnabled == True
        assert result.state == v4MicrosegConfig.SecurityPolicyState.SecurityPolicyState.MONITOR
        assert result.rules == [None]
        assert etag == "etag"

    def test_delete_security_policy_spec(self, security_policy):
        mock_policy = MagicMock(data=MagicMock(ext_id="uuid1"))
        security_policy.get_by_ext_id = MagicMock(return_value=mock_policy)
        ApiClientV4.get_api_client = MagicMock(return_value=MagicMock(get_etag=MagicMock(return_value="etag")))
        ext_id, etag = security_policy.delete_security_policy_spec("uuid1")
        assert ext_id == "uuid1"
        assert etag == "etag"
