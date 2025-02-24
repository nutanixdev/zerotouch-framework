import pytest
from unittest.mock import MagicMock, patch

from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pe_entity_v0_8 import PeEntityV0_8
from framework.scripts.python.helpers.v0_8.ha import HA
from tests.unit.config.test_data import REST_ARGS


class TestHA:

    @pytest.fixture
    def ha(self):
        self.mock_session = MagicMock(spec=RestAPIUtil)
        return HA(session=self.mock_session)

    def test_ha_init(self, ha):
        '''
        Test that the HA class is an instance of PeEntityV0_8 and that the session attribute is set correctly
        '''
        # Verify that ha_instance is an instance of HA
        assert isinstance(ha, HA)
        # Verify that ha_instance is also an instance of PeEntityV0_8
        assert isinstance(ha, PeEntityV0_8)
        # Verify that the session attribute is set correctly
        assert ha.session == self.mock_session

    def test_update_ha_reservation(self, mocker, ha):

        expected_data = {
            "enableFailover": True,
            "numHostFailuresToTolerate": 1
        }
        mock_pe_entity_v0_8_update = mocker.patch.object(PeEntityV0_8, "update",return_value={"status": "success"})
        result = ha.update_ha_reservation(enable_failover = True, num_host_failure_to_tolerate = 1)
        mock_pe_entity_v0_8_update.assert_called_once_with(data=expected_data)
        assert result == {"status": "success"}
        # Test for error handling (example)
        mock_pe_entity_v0_8_update.side_effect = ValueError("Invalid input")
        with pytest.raises(ValueError):
            ha.update_ha_reservation(enable_failover=False, num_host_failure_to_tolerate=2)
            mock_pe_entity_v0_8_update.assert_called_once_with(data=expected_data)
            
