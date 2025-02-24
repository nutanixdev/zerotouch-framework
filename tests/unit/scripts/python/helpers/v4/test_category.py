import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v4.category import Category
from unittest.mock import MagicMock, patch
from framework.helpers.v4_api_client import ApiClientV4


class TestCategory:
    @pytest.fixture
    def category(self):
        return Category()
    
    def test_category_init(self, category):
        assert category.resource_type == "prism/v4.0.b1/config/categories"
        assert category.kind == "Category"

    def test_get_categories(self, category):
        category.categories_api.list_categories = MagicMock(return_value=MagicMock(to_dict=lambda: {"data": []}))
        result = category.get_categories()
        assert result == {"data": []}
        category.categories_api.list_categories.assert_called_once()

    def test_get_category_ext_id(self, category):
        mock_category = MagicMock(data=[MagicMock(ext_id="1234")])
        category.categories_api.list_categories = MagicMock(return_value=mock_category)
        ext_id = category.get_category_ext_id("test_category", "test_value")
        assert ext_id == "1234"
        category.categories_api.list_categories.assert_called_once_with(_filter="key eq 'test_category' and value eq 'test_value'", **{'Content-Type': 'application/json', 'Accept': 'application/json'})

    def test_get_category_ext_id_not_found(self, category):
        mock_category = MagicMock(data=[])
        category.categories_api.list_categories = MagicMock(return_value=mock_category)
        ext_id = category.get_category_ext_id("test_category", "test_value")
        assert ext_id is None
        category.categories_api.list_categories.assert_called_once_with(_filter="key eq 'test_category' and value eq 'test_value'", **{'Content-Type': 'application/json', 'Accept': 'application/json'})

    def test_categories_with_values(self, category):
        category.get_categories = MagicMock(return_value={"data": [{"key": "category1", "value": "value1"}, {"key": "category1", "value": "value2"}, {"key": "category2", "value": "value3"}]})
        result = category.categories_with_values()
        expected_result = [
            {"name": "category1", "values": ["value1", "value2"]},
            {"name": "category2", "values": ["value3"]}
        ]
        assert result == expected_result
        category.get_categories.assert_called_once()

    def test_batch_values_add(self, category):
        category.batch_op.batch_create = MagicMock(return_value="batch_create_response")
        category_list = [{"name": "category1", "values": ["value1", "value2"], "description": "desc1"}]
        result = category.batch_values_add(category_list)
        expected_payload = [
            {"key": "category1", "value": "value1", "description": "desc1"},
            {"key": "category1", "value": "value2", "description": "desc1"}
        ]
        assert result == "batch_create_response"
        category.batch_op.batch_create.assert_called_once_with(request_payload_list=expected_payload)

    @patch.object(Category, 'get_category_ext_id', return_value="1234")
    def test_batch_delete_values(self, mock_get_category_ext_id, category):
        category.categories_api.get_category_by_id = MagicMock(return_value=MagicMock(data="category_data"))
        ApiClientV4.get_api_client = MagicMock(return_value=MagicMock(get_etag=MagicMock(return_value="etag_value")))
        category.batch_op.batch_delete = MagicMock(return_value="batch_delete_response")
        result = category.batch_delete_values("test_category", ["value1", "value2"])
        expected_payload = [("1234", "etag_value"), ("1234", "etag_value")]
        assert result == "batch_delete_response"
        category.batch_op.batch_delete.assert_called_once_with(expected_payload)
        mock_get_category_ext_id.assert_called()
        category.categories_api.get_category_by_id.assert_called()
        ApiClientV4.get_api_client.assert_called()



