import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.security_rule import SecurityPolicy

class TestSecurityPolicy:

    @pytest.fixture
    def security_policy(self):
        session = MagicMock(spec=RestAPIUtil)
        return SecurityPolicy(session=session)

    def test_security_policy_init(self, security_policy):
        assert security_policy.resource_type == "/network_security_rules"
        assert security_policy.kind == "network_security_rule"
        assert security_policy.session is not None

    def test_create_security_policy_spec(self, security_policy):
        sp_info = {
            "name": "test_policy",
            "description": "This is a test policy",
            "allow_ipv6_traffic": True,
            "hitlog": True,
            "app_rule": {
                "target_group": {
                    "categories": {"ADGroup": "admin_group"},
                    "default_internal_policy": "ALLOW"
                },
                "inbounds": [{"address": {"name": "test_address"}, "protocol": {"tcp": [{"start_port": 80, "end_port": 80}]}}],
                "outbounds": [{"address": {"name": "test_address"}, "protocol": {"udp": [{"start_port": 53, "end_port": 53}]}}],
                "policy_mode": "ENFORCE"
            }
        }

        mock_address_group = MagicMock()
        mock_address_group.get_uuid_by_name.return_value = "address-group-uuid"
        mock_service_group = MagicMock()
        mock_service_group.get_uuid_by_name.return_value = "service-group-uuid"

        with patch('framework.scripts.python.helpers.v3.security_rule.AddressGroup', return_value=mock_address_group), \
             patch('framework.scripts.python.helpers.v3.security_rule.ServiceGroup', return_value=mock_service_group):
            spec = security_policy.create_security_policy_spec(sp_info)

        assert spec["spec"]["name"] == "test_policy"
        assert spec["spec"]["description"] == "This is a test policy"
        assert spec["spec"]["resources"]["allow_ipv6_traffic"] is True
        assert spec["spec"]["resources"]["is_policy_hitlog_enabled"] is True
        assert spec["spec"]["resources"]["app_rule"]["target_group"]["filter"]["params"]["ADGroup"] == ["admin_group"]
        assert spec["spec"]["resources"]["app_rule"]["target_group"]["default_internal_policy"] == "ALLOW"
        assert spec["spec"]["resources"]["app_rule"]["inbound_allow_list"][0]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert spec["spec"]["resources"]["app_rule"]["outbound_allow_list"][0]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert spec["spec"]["resources"]["app_rule"]["action"] == "ENFORCE"

    def test_build_spec_rule(self, mocker, security_policy):
        MockServiceGroup = mocker.patch('framework.scripts.python.helpers.v3.security_rule.ServiceGroup')
        MockAddressGroup = mocker.patch('framework.scripts.python.helpers.v3.security_rule.AddressGroup')
        payload = {}
        rule_info = {
            "target_group": {
                "categories": {"ADGroup": "admin_group"},
                "default_internal_policy": "ALLOW"
            },
            "inbounds": [{"address": {"name": "test_address"}, "protocol": {"tcp": [{"start_port": 80, "end_port": 80}]}}],
            "outbounds": [{"address": {"name": "test_address"}, "protocol": {"udp": [{"start_port": 53, "end_port": 53}]}}],
            "policy_mode": "ENFORCE"
        }

        mock_address_group = MagicMock()
        mock_address_group.get_uuid_by_name.return_value = "address-group-uuid"
        mock_service_group = MagicMock()
        mock_service_group.get_uuid_by_name.return_value = "service-group-uuid"

        MockAddressGroup.return_value = mock_address_group
        MockServiceGroup.return_value = mock_service_group

        rule = security_policy._build_spec_rule(payload, rule_info)

        assert rule["target_group"]["filter"]["params"]["ADGroup"] == ["admin_group"]
        assert rule["target_group"]["default_internal_policy"] == "ALLOW"
        assert rule["inbound_allow_list"][0]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert rule["outbound_allow_list"][0]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert rule["action"] == "ENFORCE"

    def test_generate_bound_spec(self, mocker, security_policy):
        MockServiceGroup = mocker.patch('framework.scripts.python.helpers.v3.security_rule.ServiceGroup')
        MockAddressGroup = mocker.patch('framework.scripts.python.helpers.v3.security_rule.AddressGroup')
        payload = []
        list_of_rules = [
            {
                "address": {"name": "test_address"},
                "protocol": {"tcp": [{"start_port": 80, "end_port": 80}]}
            },
            {
                "address": {"name": "test_address_2"},
                "protocol": {"udp": [{"start_port": 53, "end_port": 53}]}
            }
        ]

        mock_address_group = MagicMock()
        mock_address_group.get_uuid_by_name.return_value = "address-group-uuid"
        mock_service_group = MagicMock()
        mock_service_group.get_uuid_by_name.return_value = "service-group-uuid"

        MockAddressGroup.return_value = mock_address_group
        MockServiceGroup.return_value = mock_service_group

        bound_spec = security_policy._generate_bound_spec(payload, list_of_rules)

        assert bound_spec[0]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert bound_spec[0]["protocol"] == "TCP"
        assert bound_spec[1]["address_group_inclusion_list"][0]["uuid"] == "address-group-uuid"
        assert bound_spec[1]["protocol"] == "UDP"
    
    def test_generate_protocol_spec(self, security_policy):
        payload = {}
        config = {
            "tcp": [{"start_port": 80, "end_port": 80}]
        }
        security_policy._generate_protocol_spec(payload, config)
        assert payload["protocol"] == "TCP"
        assert payload["tcp_port_range_list"] == [{"start_port": 80, "end_port": 80}]

        payload = {}
        config = {
            "udp": [{"start_port": 53, "end_port": 53}]
        }
        security_policy._generate_protocol_spec(payload, config)
        assert payload["protocol"] == "UDP"
        assert payload["udp_port_range_list"] == [{"start_port": 53, "end_port": 53}]

        payload = {}
        config = {
            "icmp": [{"type": 8, "code": 0}]
        }
        security_policy._generate_protocol_spec(payload, config)
        assert payload["protocol"] == "ICMP"
        assert payload["icmp_type_code_list"] == [{"type": 8, "code": 0}]

        payload = {}
        config = {
            "service": {"name": "test_service"}
        }
        mock_service_group = MagicMock()
        mock_service_group.get_uuid_by_name.return_value = "service-group-uuid"

        with patch('framework.scripts.python.helpers.v3.security_rule.ServiceGroup', return_value=mock_service_group):
            security_policy._generate_protocol_spec(payload, config)

        assert payload["service_group_list"][0]["uuid"] == "service-group-uuid"
        assert payload["service_group_list"][0]["kind"] == "service_group"
    
    def test_filter_by_uuid(self, security_policy):
        items_list = [
            {"rule_id": "123", "name": "rule1"},
            {"rule_id": "456", "name": "rule2"},
            {"rule_id": "789", "name": "rule3"}
        ]
        uuid = "456"
        result = security_policy._filter_by_uuid(uuid, items_list)
        assert result == {"rule_id": "456", "name": "rule2"}

        items_list = [
            {"rule_id": "123", "name": "rule1"},
            {"rule_id": "456", "name": "rule2"},
            {"rule_id": "789", "name": "rule3"}
        ]
        uuid = "000"
        with pytest.raises(StopIteration):
            security_policy._filter_by_uuid(uuid, items_list)



