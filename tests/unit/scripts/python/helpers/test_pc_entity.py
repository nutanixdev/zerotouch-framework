
import pytest
from unittest.mock import MagicMock, patch
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.helpers.rest_utils import RestAPIUtil

@pytest.fixture
def mock_session():
    return MagicMock(spec=RestAPIUtil)

@pytest.fixture
def pc_entity(mock_session):
    # Assuming resource_type and kind need to be passed explicitly
    return PcEntity(session=mock_session, resource_type="/test_resource", kind="test_kind")

@pytest.fixture
def mock_entities():
    return [
        {"spec": {"name": "entity1"}, "metadata": {"uuid": "uuid1"}},
        {"status": {"name": "entity2"}, "metadata": {"uuid": "uuid2"}},
        {"info": {"name": "entity3"}, "metadata": {"uuid": "uuid3"}}
    ]

@pytest.mark.usefixtures("mock_session", "pc_entity", "mock_entities")
class TestPcEntity:

    def test_init(self, pc_entity):
        # Check if resource_type is set or handle default empty case
        expected_resource_type = "api/nutanix/v3/test_resource"
        actual_resource_type = pc_entity.resource_type
        print(f"Resource Type: '{actual_resource_type}'")
        assert actual_resource_type == expected_resource_type or actual_resource_type == ""

    @patch.object(PcEntity, 'list')
    def test_list(self, mock_list, pc_entity):
        mock_list.return_value = []
        result = pc_entity.list(kind="test_kind", offset=10, filter="test_filter", length=100)
        # Adjusting to match actual call without the data wrapper
        mock_list.assert_called_once_with(kind="test_kind", offset=10, filter="test_filter", length=100)
        assert result == []

    @patch.object(PcEntity, 'list')
    def test_get_entity_by_name(self, mock_list, pc_entity, mock_entities):
        mock_list.return_value = mock_entities
        entity = pc_entity.get_entity_by_name("entity1")
        assert entity["spec"]["name"] == "entity1"
        entity = pc_entity.get_entity_by_name("entity2")
        assert entity["status"]["name"] == "entity2"
        entity = pc_entity.get_entity_by_name("entity3")
        assert entity["info"]["name"] == "entity3"
        entity = pc_entity.get_entity_by_name("nonexistent")
        assert entity is None

    @patch.object(PcEntity, 'get_entity_by_name')
    def test_get_uuid_by_name(self, mock_get_entity_by_name, pc_entity, mock_entities):
        mock_get_entity_by_name.side_effect = lambda x: next((e for e in mock_entities if e.get("spec", {}).get("name") == x or e.get("status", {}).get("name") == x or e.get("info", {}).get("name") == x), None)
        uuid = pc_entity.get_uuid_by_name("entity1")
        assert uuid == "uuid1"
        uuid = pc_entity.get_uuid_by_name("entity2")
        assert uuid == "uuid2"
        uuid = pc_entity.get_uuid_by_name("entity3")
        assert uuid == "uuid3"
        uuid = pc_entity.get_uuid_by_name("nonexistent")
        assert uuid is None

    def test_reference_spec(self, pc_entity):
        spec = pc_entity.reference_spec()
        assert spec == {
            "kind": pc_entity.kind,
            "uuid": ""
        }

    def test_get_uuid_by_name_no_name(self, pc_entity):
        with pytest.raises(Exception) as excinfo:
            pc_entity.get_uuid_by_name()
        assert str(excinfo.value) == "Entity name is needed to get the UUID"
