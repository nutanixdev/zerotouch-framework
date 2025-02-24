import pytest

from unittest.mock import mock_open, patch
from framework.scripts.python.helpers.entity import Entity

class TestEntity:

    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.mock_session = mocker.patch('framework.helpers.rest_utils.RestAPIUtil')
        self.entity = Entity(ip='127.0.0.1', username='user', password='pass', resource_type='test_resource', session=self.mock_session)

    def test_read_get(self):
        # Mock the GET response
        self.mock_session.get.return_value = {"entities": [{"id": 1, "name": "test_entity"}]}

        # Call the read method
        result = self.entity.read(uuid='1234')

        # Assert the GET method was called with the correct URI
        self.mock_session.get.assert_called_once_with('test_resource/1234')
        # Assert the response is as expected
        assert result == [{"id": 1, "name": "test_entity"}]

    def test_read_post(self):
        # Mock the POST response
        self.mock_session.post.return_value = {"entities": [{"id": 1, "name": "test_entity"}]}
        data = {"key": "value"}

        # Call the read method with POST
        result = self.entity.read(method="POST", data=data)

        # Assert the POST method was called with the correct URI and data
        self.mock_session.post.assert_called_once_with('test_resource', data=data)
        # Assert the response is as expected
        assert result == [{"id": 1, "name": "test_entity"}]

    def test_create(self):
        # Mock the POST response
        self.mock_session.post.return_value = {"id": 1, "name": "test_entity"}
        data = {"key": "value"}

        # Call the create method
        result = self.entity.create(data=data)

        # Assert the POST method was called with the correct URI and data
        self.mock_session.post.assert_called_once_with('test_resource', data=data, jsonify=True)
        # Assert the response is as expected
        assert result == {"id": 1, "name": "test_entity"}
    
    def test_update(self):
        # Mock the PUT response
        self.mock_session.put.return_value = {"id": 1, "name": "updated_entity"}
        data = {"key": "value"}
        # Call the update method
        result = self.entity.update(data=data, endpoint='test_endpoint')
        # Assert the PUT method was called with the correct URI and data
        self.mock_session.put.assert_called_once_with('test_resource/test_endpoint', data=data)
        # Assert the response is as expected
        assert result == {"id": 1, "name": "updated_entity"}

    def test_list(self):
        # Mock the GET response
        self.mock_session.post.return_value = {"entities": [{"id": 1, "name": "entity1"}, {"id": 2, "name": "entity2"}]}
        # Call the list method
        result = self.entity.list(endpoint='test_endpoint')
        # Assert the GET method was called with the correct URI
        self.mock_session.post.assert_called_once_with('test_resource/list/test_endpoint', data=None)
        # Assert the response is as expected
        assert result == [{"id": 1, "name": "entity1"}, {"id": 2, "name": "entity2"}]

    def test_upload(self):
        # Mock the POST response
        self.mock_session.post.return_value = {"status": "success"}
        source = "test_file.txt"
        data = {"key": "value"}
        # Call the upload method by mocking the open method
        mock_open_obj = mock_open(read_data='test_data')
        with patch('builtins.open', mock_open_obj):
            result = self.entity.upload(source=source, data=data)
        # Assert the POST method was called with the correct URI, data, and source file
        self.mock_session.post.assert_called_once()
        # Assert the response is as expected
        assert result == {"status": "success"}

    def test_delete(self):
        # Mock the DELETE response
        self.mock_session.delete.return_value = {"status": "success"}
        # Call the delete method
        result = self.entity.delete(endpoint='test_endpoint')
        # Assert the DELETE method was called with the correct URI
        self.mock_session.delete.assert_called_once_with('test_resource/test_endpoint')
        # Assert the response is as expected
        assert result == {"status": "success"}

    def test_get_spec(self):
        # Mock the GET response
        self.mock_session.get.return_value = {"spec": {"key": "value"}}
        # Call the get_spec method
        result = self.entity.get_spec()
        # Assert the GET method was called with the correct URI
        self.mock_session.get.assert_called_once_with('test_resource/spec')
        # Assert the response is as expected
        assert result == {"spec": {"key": "value"}}


    def test_build_url_with_query(self):
        # Call the _build_url_with_query method
        result = self.entity._build_url_with_query(url='test_url', query={'param': 'value'})
        # Assert the result is as expected
        assert result == 'test_url?param=value'

    def test_filter_entities(self):
        # Define the entities and custom filters
        entities = [{"id": 1, "name": "entity1"}, {"id": 2, "name": "entity2"}, {"id": 3, "name": "entity3"}]
        custom_filters = {"name": "entity2"}
        # Call the _filter_entities method
        result = self.entity._filter_entities(entities, custom_filters)
        # Assert the result is as expected
        assert result == [{"id": 2, "name": "entity2"}]
