import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.pc_groups_op import PcGroupsOp
from framework.helpers.rest_utils import RestAPIUtil

@pytest.fixture
def mock_session():
    return MagicMock(spec=RestAPIUtil)
 
@pytest.fixture
def pc_groups_op(mock_session):
    return PcGroupsOp(session=mock_session, base_path='mock_base_path')
 
@pytest.fixture
def mock_response():
    return {
        "group_results": [{
            "entity_results": [
                {
                    "entity_id": "mock_id_1",
                    "data": [
                        {"name": "name", "values": [{"values": ["mock_value_1"]}]}
                    ]
                },
                {
                    "entity_id": "mock_id_2",
                    "data": [
                        {"name": "name", "values": [{"values": ["mock_value_2"]}]}
                    ]
                }
            ],
            "total_entity_count": 2,
            "filtered_entity_count": 2
        }]
    }
 
class TestPcGroupsOp:
 
    def test_init(self, mock_session):
        pc = PcGroupsOp(session=mock_session)
        assert pc.session == mock_session
        assert pc.base_path is None
 
        base_path = 'mock_base_path'
        pc_with_base = PcGroupsOp(session=mock_session, base_path=base_path)
        assert pc_with_base.base_path == base_path
 
    def test_list_entities(self, pc_groups_op, mock_response):
        # Mocking the internal method to return the response
        pc_groups_op._PcGroupsOp__groups_post_call = MagicMock(return_value=mock_response)
       
        # Call the method under test
        result = pc_groups_op.list_entities(entity_type="vm", attributes=["name"])
 
        # Debugging information
        print(f"Mocked response: {mock_response}")
       
        # Extract values from the response for debugging
        response = pc_groups_op._PcGroupsOp__groups_post_call(0, 500, entity_type="vm", attributes=["name"])
        total_entity_count = response["group_results"][0].get("total_entity_count")
        filtered_entity_count = response["group_results"][0].get("filtered_entity_count")
       
        print(f"Response from __groups_post_call within test: {response}")
        print(f"Total entity count from mocked response: {total_entity_count}")
        print(f"Filtered entity count from mocked response: {filtered_entity_count}")
 
        # Assertions
        assert total_entity_count is not None, "Total entity count should not be None"
        assert filtered_entity_count is not None, "Filtered entity count should not be None"
        assert total_entity_count == 2, "Total entity count should be 2"
        assert filtered_entity_count == 2, "Filtered entity count should be 2"
       
        # Additional checks on the result
        assert len(result) == 2
        assert result[0]["uuid"] == "mock_id_1"
        assert result[0]["name"] == "mock_value_1"
        assert result[1]["uuid"] == "mock_id_2"
        assert result[1]["name"] == "mock_value_2"
 
    def test_list_dvs(self, pc_groups_op, mock_response):
        pc_groups_op.list_entities = MagicMock(return_value=pc_groups_op._PcGroupsOp__parse_response(mock_response))
        cluster_uuid = 'mock_cluster_uuid'
       
        result = pc_groups_op.list_dvs(cluster_uuid)
       
        assert len(result) == 2
        assert result[0]["uuid"] == "mock_id_1"
        assert result[1]["uuid"] == "mock_id_2"
 
    def test_list_events(self, pc_groups_op, mock_response):
        pc_groups_op.list_entities = MagicMock(return_value=pc_groups_op._PcGroupsOp__parse_response(mock_response))
        start_time = 1625097600000000
       
        result = pc_groups_op.list_events(start_time)
       
        assert len(result) == 2
        assert result[0]["uuid"] == "mock_id_1"
        assert result[1]["uuid"] == "mock_id_2"
 
    def test_list_audits(self, pc_groups_op, mock_response):
        pc_groups_op.list_entities = MagicMock(return_value=pc_groups_op._PcGroupsOp__parse_response(mock_response))
        start_time = 1625097600000000
       
        result = pc_groups_op.list_audits(start_time)
       
        assert len(result) == 2
        assert result[0]["uuid"] == "mock_id_1"
        assert result[1]["uuid"] == "mock_id_2"
 
    def test_groups_post_call(self, pc_groups_op, mock_session, mock_response):
        mock_session.post.return_value = mock_response
        group_member_offset = 0
        group_member_count = 500
        kwargs = {
            "entity_type": "vm",
            "attributes": ["name"]
        }
       
        response = pc_groups_op._PcGroupsOp__groups_post_call(group_member_offset, group_member_count, **kwargs)
       
        assert response == mock_response
        mock_session.post.assert_called_once()
 
    def test_parse_response(self, pc_groups_op, mock_response):
        response = mock_response
        result = pc_groups_op._PcGroupsOp__parse_response(response)
       
        assert len(result) == 2
        assert result[0]["uuid"] == "mock_id_1"
        assert result[0]["name"] == "mock_value_1"
        assert result[1]["uuid"] == "mock_id_2"
        assert result[1]["name"] == "mock_value_2"