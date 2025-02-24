import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v2.vm import VM
from framework.scripts.python.helpers.pe_entity_v2 import PeEntityV2
from unittest.mock import MagicMock

class TestVM:
 
    @pytest.fixture
    def vm(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return VM(session=self.session)

    def test_vm_init(self, vm):
        assert vm.resource_type == "/vms"
        assert vm.session == self.session
        assert isinstance(vm, VM)
        assert isinstance(vm, PeEntityV2)