import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.prism_central import PrismCentral

class TestPrismCentral:

    @pytest.fixture
    def prism_central(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return PrismCentral(session=self.session)

    def test_prism_central_init(self, prism_central):
        '''
        Test that the PrismCentral class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert prism_central.resource_type == "/prism_central"
        assert prism_central.session == self.session
        assert isinstance(prism_central, PrismCentral)
        assert isinstance(prism_central, PcEntity)

    def test_prism_central_kind(self, prism_central):
        '''
        Test that the kind attribute is set correctly
        '''
        assert prism_central.kind == "prism_central"