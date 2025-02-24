import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.v3.vm import VM, VmPowerState

@pytest.fixture
def vm(mocker):
    session = mocker.MagicMock()
    return VM(session)


class TestVM:
    def test_vm_init(self, vm):
        assert vm.resource_type == "/vms"
        assert vm.kind == "vm"
        assert vm.session is not None

    def test_batch_create_vm(self, vm, mocker):
        mock_batch_create = mocker.patch.object(vm.batch_op, 'batch_create', return_value={"status": "success"})

        response = vm.batch_create_vm(vm_create_payload_list=[{"spec": {"name": "test_vm"}}])

        assert response == {"status": "success"}
        mock_batch_create.assert_called_once_with(request_payload_list=[{"spec": {"name": "test_vm"}}])

    def test_get_uuid_by_name(self, vm, mocker):
        mock_get_uuid_by_name = mocker.patch.object(VM, 'get_uuid_by_name', return_value="uuid123")

        uuid = vm.get_uuid_by_name(cluster_name="test_cluster", vm_name="test_vm")

        assert uuid == "uuid123"
        mock_get_uuid_by_name.assert_called_once_with(cluster_name="test_cluster", vm_name="test_vm")

    def test_batch_power_on_vm(self, vm, mocker):
        mock_batch_update = mocker.patch.object(vm.batch_op, 'batch_update', return_value={"status": "success"})

        response = vm.batch_power_on_vm(vm_payload_list=[{"spec": {"name": "test_vm", "resources": {}}}])

        assert response == {"status": "success"}
        updated_payload = [{"spec": {"name": "test_vm", "resources": {"power_state": VmPowerState.ON}}}]
        mock_batch_update.assert_called_once_with(updated_payload)

    def test_batch_delete_vm(self, vm, mocker):
        mock_batch_delete = mocker.patch.object(vm.batch_op, 'batch_delete', return_value={"status": "success"})

        response = vm.batch_delete_vm(uuid_list=["uuid1", "uuid2"])

        assert response == {"status": "success"}
        mock_batch_delete.assert_called_once_with(entity_list=["uuid1", "uuid2"])

    def test_get_vm_ip_address(self):
        vm_info = {
            "status": {
                "resources": {
                    "nic_list": [
                        {
                            "ip_endpoint_list": [
                                {"ip": "192.168.1.1"},
                                {"ip": "192.168.1.2"}
                            ]
                        }
                    ]
                }
            }
        }
        ip_addresses = VM._get_vm_ip_address(vm_info)
        assert ip_addresses == ["192.168.1.1", "192.168.1.2"]

    def test_filter_vm_by_uuid(self):
        vm_list = [
            {"metadata": {"uuid": "uuid1"}},
            {"metadata": {"uuid": "uuid2"}},
            {"metadata": {"uuid": "uuid3"}}
        ]
        uuid_list = ["uuid1", "uuid3"]
        filtered_vms = VM._filter_vm_by_uuid(vm_list, uuid_list)
        assert filtered_vms == [
            {"metadata": {"uuid": "uuid1"}},
            {"metadata": {"uuid": "uuid3"}}
        ]