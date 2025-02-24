import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.pulse import Pulse
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestPulse:
    @pytest.fixture
    def pulse(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return Pulse(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_pulse_init(self, pulse):
        assert pulse.resource_type == "/pulse"
        assert pulse.session == self.session
        assert pulse.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(pulse, Pulse)
        assert isinstance(pulse, PeEntityV1)
    
    def test_update_pulse(self, mocker, pulse):
        # Test when Pulse is enabled
        
        mock_update = mocker.patch.object(PeEntityV1, "update")
        pulse.update_pulse(enable=True)
        mock_update.assert_called_once_with(
            data={"enable": True, "isPulsePromptNeeded": False}
            )

        # Test when Pulse is disabled
        pulse.update_pulse(enable=False)
        mock_update.assert_called_with(
            data={"enable": False, "isPulsePromptNeeded": False}
            )

