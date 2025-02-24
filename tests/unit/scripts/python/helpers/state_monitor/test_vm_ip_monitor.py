import pytest
from framework.scripts.python.helpers.state_monitor.vm_ip_monitor import VmIpMonitor
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v3.vm import VM
from framework.scripts.python.helpers.state_monitor.state_monitor import StateMonitor
from unittest.mock import MagicMock

class TestVmIpMonitor:
    @pytest.fixture
    def vm_ip_monitor(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return VmIpMonitor(
            session=self.session,
            vm_uuid_list=["test_uuid1", "test_uuid2"]
            )

    def test_vm_ip_monitor_init(self, vm_ip_monitor):
        assert isinstance(vm_ip_monitor, VmIpMonitor)
        assert isinstance(vm_ip_monitor, StateMonitor)
        assert vm_ip_monitor.session == self.session
        assert vm_ip_monitor.vm_uuid_list == ["test_uuid1", "test_uuid2"]

    def test_check_status(self, vm_ip_monitor, mocker):
        mock_vm_list = mocker.patch.object(VM, 'list')
        mock_vm_list.return_value = [{"metadata": {"uuid": "test_uuid1"}},{"metadata": {"uuid": "test_uuid3"}}]
        mock_get_vm_ip_address = mocker.patch.object(VM, '_get_vm_ip_address')
        mock_get_vm_ip_address.return_value = ["test_ip1"]
        assert vm_ip_monitor.check_status() == (None, True)
        mock_get_vm_ip_address.return_value = []
        assert vm_ip_monitor.check_status() == ([{"metadata": {"uuid": "test_uuid1"}}], False)        