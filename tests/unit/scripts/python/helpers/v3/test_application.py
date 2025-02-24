import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.application import Application

class TestApplication:

    @pytest.fixture
    def application(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Application(session=self.session)

    def test_application_init(self, application):
        '''
        Test that the Application class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert application.resource_type == "/apps"
        assert application.session == self.session
        assert isinstance(application, Application)
        assert isinstance(application, PcEntity)