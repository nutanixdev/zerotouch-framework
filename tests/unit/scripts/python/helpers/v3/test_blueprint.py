import pytest
from unittest.mock import MagicMock
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.blueprint import Blueprint

class TestBlueprint:

    @pytest.fixture
    def blueprint(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Blueprint(session=self.session)

    def test_blueprint_init(self, blueprint):
        '''
        Test that the Blueprint class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert blueprint.resource_type == "/blueprints"
        assert blueprint.session == self.session
        assert isinstance(blueprint, Blueprint)
        assert isinstance(blueprint, PcEntity)

    def test_list_default_filter(self, blueprint, mocker):
        expected_response = [{"name": "test_blueprint"}]
        mock_list = mocker.patch.object(PcEntity, 'list', return_value=expected_response)

        response = blueprint.list()

        mock_list.assert_called_once_with(filter='state!=DELETED')
        assert response == expected_response

    def test_list_custom_filter(self, blueprint, mocker):
        custom_filter = 'name==test'
        expected_response = [{"name": "test_blueprint"}]
        mock_list = mocker.patch.object(PcEntity, 'list', return_value=expected_response)

        response = blueprint.list(filters=custom_filter)

        mock_list.assert_called_once_with(filter=custom_filter)
        assert response == expected_response
