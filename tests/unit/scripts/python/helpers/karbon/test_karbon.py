import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.karbon.karbon import Karbon
from framework.helpers.rest_utils import RestAPIUtil



class TestKarbon:
    @pytest.fixture
    def karbon(self):
        self.session = MagicMock(RestAPIUtil=MagicMock())
        return Karbon(session=self.session, resource_type="test_resource")
        
    def test_karbon_init(self, karbon):
        assert karbon.resource == "karbontest_resource"
        assert karbon.session == self.session