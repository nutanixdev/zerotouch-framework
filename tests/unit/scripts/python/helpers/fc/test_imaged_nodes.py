import pytest
from framework.scripts.python.helpers.fc.imaged_nodes import ImagedNode
from framework.scripts.python.helpers.fc_entity import FcEntity
from framework.helpers.rest_utils import RestAPIUtil
from unittest.mock import MagicMock, patch

class TestImagedNode:
    @pytest.fixture
    def imaged_node(self):
        return ImagedNode(session=MagicMock(spec=RestAPIUtil))
    
    def test_imaged_node_init(self, imaged_node):
        assert imaged_node.resource_type == "/imaged_nodes"
        assert isinstance(imaged_node, ImagedNode)
        assert isinstance(imaged_node, FcEntity)
        assert imaged_node.build_spec_methods == {"filters": imaged_node._build_spec_filters}    

    def test_build_spec_filters(self, imaged_node):
        payload = {}
        value = "test_value"
        assert imaged_node._build_spec_filters(payload, value) == ({"filters": value}, None)
    
    def test_get_default_spec(self, imaged_node):
        assert imaged_node._get_default_spec() == {"filters": {"node_state": ""}}
    
    def test_node_details_by_block_serial(self, imaged_node, mocker):
        mock_list = mocker.patch.object(ImagedNode, 'list')
        mock_list.return_value = [
            {"block_serial": "test_block_serial"},
            {"block_serial": "test_block_serial_2"},
            {"block_serial": "test_block_serial_3"}
            ]
        block_serials = ["test_block_serial", "test_block_serial_2"]
        assert imaged_node.node_details_by_block_serial(block_serials) == (
            [{"block_serial": "test_block_serial"}, {"block_serial": "test_block_serial_2"}], None
            )
        
    def test_node_details(self, imaged_node, mocker):
        mock_list = mocker.patch.object(ImagedNode, 'list')
        mock_list.return_value = [
            {"block_serial": "test_block_serial"},
            {"block_serial": "test_block_serial_2"}, {"block_serial": "test_block_serial_3"}]
        assert imaged_node.node_details() ==[
                {"block_serial": "test_block_serial"},
                {"block_serial": "test_block_serial_2"},
                {"block_serial": "test_block_serial_3"}
                ]
    
    def test_node_details_by_node_serial(self, imaged_node, mocker):
        mock_node_details = mocker.patch.object(ImagedNode, 'node_details')
        mock_node_details.return_value = [   
                {"node_serial": "test_node_serial"},
                {"node_serial": "test_node_serial_2"},
                {"node_serial": "test_node_serial_3"}
            ]
        node_serial_list = ["test_node_serial", "test_node_serial_2"]
        assert imaged_node.node_details_by_node_serial(node_serial_list) == {
            "test_node_serial": {"node_serial": "test_node_serial"},
            "test_node_serial_2": {"node_serial": "test_node_serial_2"}
            }