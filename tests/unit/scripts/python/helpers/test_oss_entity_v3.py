import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.entity import Entity
from framework.scripts.python.helpers.pc_groups_op import PcGroupsOp
from framework.scripts.python.helpers.oss_entity_v3 import OssEntityOp

@pytest.fixture
def session():
    return MagicMock(spec=RestAPIUtil)

@pytest.fixture
def oss_entity_op(session):
    return OssEntityOp(session=session)

class TestOssEntityOp:
    def test_oss_entity_op_init(self, oss_entity_op):
        assert oss_entity_op.resource_type == "oss/api/nutanix/v3"
        assert oss_entity_op.session is not None

    @patch.object(PcGroupsOp, 'list_entities')
    def test_list_default(self, mock_list_entities, oss_entity_op):
        mock_list_entities.return_value = [{"name": "entity1"}, {"name": "entity2"}]

        response = oss_entity_op.list()
        assert response == [{"name": "entity1"}, {"name": "entity2"}]

        mock_list_entities.assert_called_once_with(
            entity_type=oss_entity_op.kind,
            attributes=[],
            filter_criteria=None
        )

    @patch.object(PcGroupsOp, 'list_entities')
    def test_list_with_params(self, mock_list_entities, oss_entity_op):
        mock_list_entities.return_value = [{"name": "entity1"}, {"name": "entity2"}]

        response = oss_entity_op.list(
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test"
        )
        assert response == [{"name": "entity1"}, {"name": "entity2"}]

        mock_list_entities.assert_called_once_with(
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test"
        )

    @patch.object(PcGroupsOp, 'list_entities')
    def test_list_with_base_path(self, mock_list_entities, oss_entity_op):
        mock_list_entities.return_value = [{"name": "entity1"}, {"name": "entity2"}]

        response = oss_entity_op.list(
            base_path="custom/base/path",
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test"
        )
        assert response == [{"name": "entity1"}, {"name": "entity2"}]

        mock_list_entities.assert_called_once_with(
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test",
            base_path="custom/base/path"
        )

    @patch.object(PcGroupsOp, 'list_entities')
    def test_list_with_query_str(self, mock_list_entities, oss_entity_op):
        mock_list_entities.return_value = [{"name": "entity1"}, {"name": "entity2"}]

        response = oss_entity_op.list(
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test",
            query_str="test_query"
        )
        assert response == [{"name": "entity1"}, {"name": "entity2"}]

        mock_list_entities.assert_called_once_with(
            entity_type="bucket",
            attributes=["name", "uuid"],
            filter_criteria="name==test",
            query_str="test_query"
        )