import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.virtual_switch import VirtualSwitch
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestVirtualSwitch:
    @pytest.fixture
    def virtual_switch(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return VirtualSwitch(session=self.session)
    
    def test_virtual_switch_init(self, virtual_switch):
        assert virtual_switch.resource_type == "/networking/v2.a1/dvs/virtual-switches"
        assert virtual_switch.session == self.session
        assert isinstance(virtual_switch, VirtualSwitch)
        assert isinstance(virtual_switch, PeEntityV1)
        
    def test_get_vs_uuid(self, mocker, virtual_switch):
        # Test when virtual switch name is found
        vs_name = "test_vs"
        vs_uuid = "test_uuid"
        vs_response = [{"data": {"name": vs_name, "extId": vs_uuid}}]
        
        mock_read = mocker.patch.object(PeEntityV1, "read", return_value=vs_response)
        result = virtual_switch.get_vs_uuid(name=vs_name)
        mock_read.assert_called_once()
        assert result == vs_uuid
        
        # Test when virtual switch name is not found
        vs_name = "unknown_vs"
        mock_read.return_value = [{"data": {"name": "test_vs", "extId": "test_uuid"}}]
        with pytest.raises(Exception) as exc:
            virtual_switch.get_vs_uuid(name=vs_name)
        assert str(exc.value) == f"Could not fetch the UUID of the entity {type(virtual_switch).__name__} with name {vs_name}"