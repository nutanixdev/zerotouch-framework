import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.recovery_plan import RecoveryPlan
from framework.scripts.python.helpers.pc_entity import PcEntity

class TestRecoveryPlan:

    @pytest.fixture
    def recovery_plan(self):
        session = MagicMock(spec=RestAPIUtil)
        return RecoveryPlan(session=session)

    def test_recovery_plan_init(self, recovery_plan):
        assert recovery_plan.resource_type == "/recovery_plans"
        assert recovery_plan.kind == "recovery_plan"
        assert recovery_plan.source_pe_clusters is None
        assert recovery_plan.primary_location_cluster_list is None
        assert recovery_plan.recovery_location_cluster_list is None
        assert recovery_plan.primary_location is None
        assert recovery_plan.primary_location_url is None
        assert recovery_plan.recovery_location_url is None
        assert recovery_plan.remote_pe_clusters is None

    def test_get_payload(self, recovery_plan, mocker):
        rp_spec = {"name": "test_rule"}
        source_pe_clusters = {"source_ip": {"cluster1": "uuid1"}}
        remote_pe_clusters = {"remote_ip": {"cluster2": "uuid2"}}

        mock_get_spec = mocker.patch.object(PcEntity, 'get_spec', return_value=({"spec": "payload"}, None))

        payload = recovery_plan.get_payload(rp_spec, source_pe_clusters, remote_pe_clusters)


        mock_get_spec.assert_called_once_with(params=rp_spec)
        mock_get_spec.return_value = (None, "error_message")
        with pytest.raises(Exception) as excinfo:
            recovery_plan.get_payload(rp_spec, source_pe_clusters, remote_pe_clusters)

        assert "Failed generating recovery-plan spec: error_message" in str(excinfo.value)


    def test_build_spec_stages(self, recovery_plan, mocker):
        mock_convert_to_secs = mocker.patch('framework.helpers.general_utils.convert_to_secs', return_value=60)
        MockAvailabilityZone = mocker.patch('framework.scripts.python.helpers.v3.recovery_plan.AvailabilityZone')
        payload = recovery_plan._get_default_spec()
        stages = [{
            "vms": [{"name": "vm1"}],
            "categories": [{"key": "category1", "value": "value1"}],
            "delay": 60
        }]

        mock_vm_ref = mocker.patch.object(recovery_plan, 'get_vm_reference_spec', return_value=({"kind": "vm", "name": "vm1", "uuid": "uuid1"}, None))

        updated_payload, error = recovery_plan._build_spec_stages(payload, stages)

        print(f"Stages: {stages}")
        print(f"Updated Payload: {updated_payload}")
        print(f"Error: {error}")

        assert error is None


    def test_build_spec_network_mappings(self, mocker, recovery_plan):
        mock_convert_to_secs = mocker.patch('framework.helpers.general_utils.convert_to_secs')
        MockAvailabilityZone = mocker.patch('framework.scripts.python.helpers.v3.recovery_plan.AvailabilityZone')
        payload = recovery_plan._get_default_spec()
        network_mappings = [{
            "primary": {"prod": {"name": "primary_prod", "gateway_ip": "10.0.0.1", "prefix": "24"}},
            "recovery": {"prod": {"name": "recovery_prod", "gateway_ip": "10.0.1.1", "prefix": "24"}}
        }]
        recovery_plan.primary_location_url = "http://primary_location"
        recovery_plan.recovery_location_url = "http://recovery_location"

        updated_payload, error = recovery_plan._build_spec_network_mappings(payload, network_mappings)

        print(f"Network Mappings: {network_mappings}")
        print(f"Updated Payload: {updated_payload}")
        print(f"Error: {error}")

        assert error is None
        
    def test_build_spec_primary_location(self, mocker, recovery_plan):
        mock_az = mocker.patch('framework.scripts.python.helpers.v3.recovery_plan.AvailabilityZone')
        # Mocking return value of get_mgmt_url_by_name
        mock_az.return_value.get_mgmt_url_by_name.return_value = "mocked_local_az_url"

        # Input payload and primary_location data
        payload = {
            "spec": {
                "resources": {
                    "parameters": {
                        "primary_location_index": 0,
                        "availability_zone_list": [{}]
                    }
                }
            }
        }
        primary_location = {
            "availability_zone": "availability_zone_ip"
        }

        recovery_plan.source_pe_clusters = {"cluster_name": {"uuid": "cluster_uuid"}}
        # Call the method
        result, _ = recovery_plan._build_spec_primary_location(payload, primary_location)

        # Assertions
        mock_az.return_value.get_mgmt_url_by_name.assert_called_once_with("Local AZ")
        print(f"Result: {result}")
        assert result == {'spec': {'resources': {'parameters': {
            'primary_location_index': 0,
            'availability_zone_list': [{'availability_zone_url': 'mocked_local_az_url'}]
            }}}}
        

    def test_build_spec_recovery_location(self, mocker, recovery_plan):
        mock_az = mocker.patch('framework.scripts.python.helpers.v3.recovery_plan.AvailabilityZone')
        # Mocking return value of get_mgmt_url_by_name
        mock_az.return_value.get_mgmt_url_by_name.side_effect = [
            "mocked_local_az_url", "mocked_recovery_az_url"
        ]

        # Input payload and recovery_location data
        payload = {
            "spec": {
                "resources": {
                    "parameters": {
                        "primary_location_index": 0,
                        "availability_zone_list": {}
                    }
                }
            }
        }
        recovery_location = {
            "cluster": "cluster_name",
            "availability_zone": "availability_zone_ip"
        }
        
        recovery_plan.primary_location = {
            "availability_zone": "availability_zone_ip"
        }
        recovery_plan.source_pe_clusters = {"availability_zone_ip": {"cluster_name": "cluster_uuid"}}
        # Call the method
        result, _ = recovery_plan._build_spec_recovery_location(payload, recovery_location)

        # Assertions
        mock_az.return_value.get_mgmt_url_by_name.assert_called_with("Local AZ")
        print(result)
        assert result == {'spec': {'resources': {'parameters': {
            'primary_location_index': 0, 'availability_zone_list': {
                1: {'availability_zone_url': 'mocked_local_az_url',
                    'cluster_reference_list': [
                        {'kind': 'cluster', 'uuid': 'cluster_uuid'}
                        ]}
                }}
                                                 }}}

    def test_build_spec_floating_ip_assignments(self, mocker, recovery_plan):
        mock_convert_to_secs = mocker.patch('framework.helpers.general_utils.convert_to_secs')
        MockAvailabilityZone = mocker.patch('framework.scripts.python.helpers.v3.recovery_plan.AvailabilityZone')
        payload = recovery_plan._get_default_spec()
        floating_ip_assignments = [{
            "availability_zone_url": "http://zone1",
            "vm_ip_assignments": [{
                "vm": {"name": "vm1"},
                "vm_nic_info": {"uuid": "nic1", "ip": "10.0.0.2"},
                "test_ip_config": {"ip": "10.0.0.3"},
                "prod_ip_config": {"ip": "10.0.1.2"}
            }]
        }]

        mock_vm_ref = mocker.patch.object(recovery_plan, 'get_vm_reference_spec', return_value=({"kind": "vm", "name": "vm1", "uuid": "uuid1"}, None))

        updated_payload, error = recovery_plan._build_spec_floating_ip_assignments(payload, floating_ip_assignments)

        print(f"Floating IP Assignments: {floating_ip_assignments}")
        print(f"Updated Payload: {updated_payload}")
        print(f"Error: {error}")

        assert error is None
    
    def test_get_vm_reference_spec(self, recovery_plan):
        vm_config = {"name": "vm1", "uuid": "uuid1"}
        vm_ref, error = recovery_plan.get_vm_reference_spec(vm_config)

        assert vm_ref == {"kind": "vm", "name": "vm1", "uuid": "uuid1"}
        assert error is None

        vm = {}
        vm_ref, error = recovery_plan.get_vm_reference_spec(vm)

        assert vm_ref is None
        assert error == "Provide name or uuid for building vm reference spec"