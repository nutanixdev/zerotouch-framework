import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.protection_rule import ProtectionRule
from framework.scripts.python.helpers.pc_entity import PcEntity

class TestProtectionRule:

    @pytest.fixture
    def protection_rule(self):
        session = MagicMock(spec=RestAPIUtil)
        return ProtectionRule(session=session)

    def test_protection_rule_init(self, protection_rule):
        assert protection_rule.resource_type == "/protection_rules"
        assert protection_rule.kind == "protection_rule"
        assert protection_rule.source_pe_clusters is None
        assert protection_rule.remote_pe_clusters is None
        assert isinstance(protection_rule, ProtectionRule)
        assert isinstance(protection_rule, PcEntity)

    def test_get_payload(self, protection_rule, mocker):
        pr_spec = {"name": "test_rule"}
        source_pe_clusters = {"source_ip": {"cluster1": "uuid1"}}
        remote_pe_clusters = {"remote_ip": {"cluster2": "uuid2"}}

        mock_get_spec = mocker.patch.object(PcEntity, 'get_spec', return_value=({"spec": "payload"}, None))

        payload = protection_rule.get_payload(pr_spec, source_pe_clusters, remote_pe_clusters)

        print(f"Mock get_spec call count: {mock_get_spec.call_count}")
        print(f"Mock get_spec call args: {mock_get_spec.call_args}")

        mock_get_spec.assert_called_once_with(params=pr_spec)
        assert payload == {"spec": "payload"}

        mock_get_spec.return_value = (None, "error_message")

        with pytest.raises(Exception) as excinfo:
            protection_rule.get_payload(pr_spec, source_pe_clusters, remote_pe_clusters)

        print(f"Raised Exception: {str(excinfo.value)}")
        assert str(excinfo.value) == "Failed generating protection-rule spec: error_message"


    def test_build_spec_schedules(self, mocker, protection_rule):
        mock_convert_to_secs = mocker.patch('framework.scripts.python.helpers.v3.protection_rule.convert_to_secs')
        MockAvailabilityZone = mocker.patch('framework.scripts.python.helpers.v3.protection_rule.AvailabilityZone')
        payload = ProtectionRule._get_default_spec()
        schedules = [{
            "source": {"availability_zone": "local_az", "clusters": ["cluster1"]},
            "destination": {"availability_zone": "remote_az", "cluster": "cluster2"},
            "protection_type": "ASYNC",
            "rpo": 15,
            "rpo_unit": "MINUTES",
            "snapshot_type": "CRASH_CONSISTENT",
            "local_retention_policy": {"num_snapshots": 5}
        }]
        source_pe_clusters = {"local_az": {"cluster1": "uuid1"}}
        remote_pe_clusters = {"remote_az": {"cluster2": "uuid2"}}

        mock_az_instance = MockAvailabilityZone.return_value
        mock_az_instance.get_mgmt_url_by_name.return_value = "http://localhost:9440/PrismGateway/services/rest/v2.0/"

        mock_convert_to_secs.return_value = (900, None)  # 15 minutes in seconds

        protection_rule.source_pe_clusters = source_pe_clusters
        protection_rule.remote_pe_clusters = remote_pe_clusters
        updated_payload, error = protection_rule._build_spec_schedules(payload, schedules)

        print(f"Schedules: {schedules}")
        print(f"Source PE Clusters: {source_pe_clusters}")
        print(f"Remote PE Clusters: {remote_pe_clusters}")
        print(f"Mock convert_to_secs return value: {mock_convert_to_secs.return_value}")
        print(f"Updated Payload: {updated_payload}")
        print(f"Error: {error}")

        assert error is None

    def test_build_spec_name(self, protection_rule):
        payload = ProtectionRule._get_default_spec()
        name = "test_rule"
        updated_payload, error = protection_rule._build_spec_name(payload, name)
        assert updated_payload["spec"]["name"] == name
        assert error is None

    def test_build_spec_desc(self, protection_rule):
        payload = ProtectionRule._get_default_spec()
        desc = "test_description"
        updated_payload, error = protection_rule._build_spec_desc(payload, desc)
        assert updated_payload["spec"]["description"] == desc
        assert error is None

    def test_build_spec_start_time(self, protection_rule):
        payload = ProtectionRule._get_default_spec()
        start_time = "2023-01-01T00:00:00Z"
        updated_payload, error = protection_rule._build_spec_start_time(payload, start_time)
        assert updated_payload["spec"]["resources"]["start_time"] == start_time
        assert error is None

    def test_build_spec_protected_categories(self, protection_rule):
        payload = ProtectionRule._get_default_spec()
        categories = [{"key": "category_key", "value": "category_value"}]
        updated_payload, error = protection_rule._build_spec_protected_categories(payload, categories)
        assert updated_payload["spec"]["resources"]["category_filter"]["params"] == categories
        assert error is None

'''import unittest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.helpers.general_utils import convert_to_secs
from framework.scripts.python.helpers.v3.protection_rule import ProtectionRule


class TestProtectionRule(unittest.TestCase):
    def setUp(self):
        self.session = RestAPIUtil()
        self.protection_rule = ProtectionRule(self.session)

    def test_get_payload(self):
        pr_spec = {
            "name": "Test Protection Rule",
            "desc": "This is a test protection rule",
            "start_time": "2022-01-01T00:00:00Z",
            "protected_categories": ["category1", "category2"],
            "schedules": [
                {
                    "protection_type": "ASYNC",
                    "rpo": 1,
                    "rpo_unit": "hours",
                    "snapshot_type": "FULL",
                    "local_retention_policy": "7D",
                    "remote_retention_policy": "14D",
                },
                {
                    "protection_type": "SYNC",
                    "auto_suspend_timeout": 3600,
                },
            ],
        }
        source_pe_clusters = {}
        remote_pe_clusters = {}
        expected_payload = {
            "api_version": "3.1.0",
            "metadata": {"kind": "protection_rule"},
            "spec": {
                "resources": {
                    "availability_zone_connectivity_list": [
                        {
                            "source_availability_zone_index": 0,
                            "destination_availability_zone_index": 1,
                            "snapshot_schedule_list": [
                                {
                                    "recovery_point_objective_secs": 3600,
                                    "snapshot_type": "FULL",
                                    "local_snapshot_retention_policy": "7D",
                                    "remote_snapshot_retention_policy": "14D",
                                }
                            ],
                        },
                        {
                            "source_availability_zone_index": 1,
                            "destination_availability_zone_index": 0,
                            "snapshot_schedule_list": [
                                {
                                    "recovery_point_objective_secs": 0,
                                    "auto_suspend_timeout_secs": 3600,
                                }
                            ],
                        },
                    ],
                    "ordered_availability_zone_list": [],
                    "category_filter": {
                        "params": ["category1", "category2"],
                        "type": "CATEGORIES_MATCH_ANY",
                    },
                    "primary_location_list": [0],
                },
                "name": "Test Protection Rule",
            },
        }

        self.protection_rule.source_pe_clusters = source_pe_clusters
        self.protection_rule.remote_pe_clusters = remote_pe_clusters

        payload = self.protection_rule.get_payload(pr_spec, source_pe_clusters, remote_pe_clusters)

        self.assertEqual(payload, expected_payload)

    def test_build_spec_name(self):
        payload = {"spec": {"name": None}}
        name = "Test Protection Rule"
        expected_payload = {"spec": {"name": "Test Protection Rule"}}

        new_payload, _ = self.protection_rule._build_spec_name(payload, name)

        self.assertEqual(new_payload, expected_payload)

    def test_build_spec_desc(self):
        payload = {"spec": {"description": None}}
        desc = "This is a test protection rule"
        expected_payload = {"spec": {"description": "This is a test protection rule"}}

        new_payload, _ = self.protection_rule._build_spec_desc(payload, desc)

        self.assertEqual(new_payload, expected_payload)

    def test_build_spec_start_time(self):
        payload = {"spec": {"resources": {"start_time": None}}}
        start_time = "2022-01-01T00:00:00Z"
        expected_payload = {"spec": {"resources": {"start_time": "2022-01-01T00:00:00Z"}}}

        new_payload, _ = self.protection_rule._build_spec_start_time(payload, start_time)

        self.assertEqual(new_payload, expected_payload)

    def test_build_spec_protected_categories(self):
        payload = {"spec": {"resources": {"category_filter": {"params": None}}}}
        categories = ["category1", "category2"]
        expected_payload = {"spec": {"resources": {"category_filter": {"params": ["category1", "category2"]}}}}

        new_payload, _ = self.protection_rule._build_spec_protected_categories(payload, categories)

        self.assertEqual(new_payload, expected_payload)

    def test_build_spec_schedules(self):
        payload = {"spec": {"resources": {"ordered_availability_zone_list": []}}}
        schedules = [
            {
                "protection_type": "ASYNC",
                "rpo": 1,
                "rpo_unit": "hours",
                "snapshot_type": "FULL",
                "local_retention_policy": "7D",
                "remote_retention_policy": "14D",
            },
            {
                "protection_type": "SYNC",
                "auto_suspend_timeout": 3600,
            },
        ]
        expected_payload = {
            "spec": {
                "resources": {
                    "ordered_availability_zone_list": [],
                    "availability_zone_connectivity_list": [
                        {
                            "source_availability_zone_index": 0,
                            "destination_availability_zone_index": 1,
                            "snapshot_schedule_list": [
                                {
                                    "recovery_point_objective_secs": 3600,
                                    "snapshot_type": "FULL",
                                    "local_snapshot_retention_policy": "7D",
                                    "remote_snapshot_retention_policy": "14D",
                                }
                            ],
                        },
                        {
                            "source_availability_zone_index": 1,
                            "destination_availability_zone_index": 0,
                            "snapshot_schedule_list": [
                                {
                                    "recovery_point_objective_secs": 0,
                                    "auto_suspend_timeout_secs": 3600,
                                }
                            ],
                        },
                    ],
                    "category_filter": {
                        "params": [],
                        "type": "CATEGORIES_MATCH_ANY",
                    },
                    "primary_location_list": [0],
                }
            }
        }

        new_payload, _ = self.protection_rule._build_spec_schedules(payload, schedules)

        self.assertEqual(new_payload, expected_payload)


if __name__ == "__main__":
    unittest.main()'''