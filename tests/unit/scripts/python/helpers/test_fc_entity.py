import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.fc_entity import FcEntity
from framework.scripts.python.helpers.entity import Entity


class TestFcEntity:
    @pytest.fixture
    def fc_entity(self):
        self.session = MagicMock()
        self.resource_type = "/test_resource"
        return FcEntity(session=self.session, resource_type=self.resource_type)

    def test_fc_entity_init(self, fc_entity):
        assert fc_entity.session == self.session
        assert fc_entity.resource == f"api/fc/v1{self.resource_type}"
        assert isinstance(fc_entity, FcEntity)
        assert isinstance(fc_entity, Entity)

