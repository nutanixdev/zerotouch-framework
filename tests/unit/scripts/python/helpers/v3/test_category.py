import pytest
from unittest.mock import MagicMock, patch
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.pc_entity import PcEntity
from framework.scripts.python.helpers.v3.category import Category

class TestCategory:

    @pytest.fixture
    def category(self):
        self.session = MagicMock(spec=RestAPIUtil)
        return Category(session=self.session)

    def test_category_init(self, category):
        '''
        Test that the Category class is an instance of PcEntity and
        that the resource_type attribute is set correctly
        '''
        assert category.resource_type == "/categories"
        assert category.session == self.session
        assert isinstance(category, Category)
        assert isinstance(category, PcEntity)

    def test_get_values(self, category, mocker):
        category_name = "test_category"
        expected_values = [
            {'policy_counts': '{}', 'uuid': 'f312d033-c03e-47f3-b77b-78e7ee5e3430', 'value': '2', 'entity_counts': '{}'}
        ]
        mock_list = mocker.patch.object(PcEntity, 'list', return_value=expected_values)

        values = category.get_values(name=category_name)

        mock_list.assert_called_once_with(use_base_url=True, endpoint=f"{category_name}/list")
        assert values == expected_values

    def test_categories_with_values(self, category, mocker):
        category_entity_list = [
            {"name": "test_category"}
        ]
        expected_values = [
            {'policy_counts': '{}', 'uuid': 'f312d033-c03e-47f3-b77b-78e7ee5e3430', 'value': '2', 'entity_counts': '{}'}
        ]
        mock_list = mocker.patch.object(PcEntity, 'list', side_effect=[category_entity_list, expected_values])

        categories = category.categories_with_values()

        assert categories[0]["values"] == ['2']

    def test_batch_values_add(self, category, mocker):
        category_list = [
            {"name": "test_category", "values": ["value1", "value2"]}
        ]
        mock_batch = mocker.patch.object(category.batch_op, 'batch')

        category.batch_values_add(category_list=category_list)

        expected_requests = [
            {
                "operation": "PUT",
                "body": {"value": "value1", "description": "test_category"},
                "path_and_params": "api/nutanix//v3/categories/test_category/value1"
            },
            {
                "operation": "PUT",
                "body": {"value": "value2", "description": "test_category"},
                "path_and_params": "api/nutanix//v3/categories/test_category/value2"
            }
        ]
        mock_batch.assert_called_once_with(api_request_list=expected_requests)

    def test_batch_delete_values(self, category, mocker):
        category_name = "test_category"
        values = ["value1", "value2"]
        mock_batch = mocker.patch.object(category.batch_op, 'batch')

        category.batch_delete_values(category_name=category_name, values=values)

        expected_requests = [
            {
                "operation": "DELETE",
                "path_and_params": "api/nutanix//v3/categories/test_category/value1"
            },
            {
                "operation": "DELETE",
                "path_and_params": "api/nutanix//v3/categories/test_category/value2"
            }
        ]
        mock_batch.assert_called_once_with(api_request_list=expected_requests)

