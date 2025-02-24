import pytest
from unittest.mock import patch, MagicMock
from framework.scripts.python.helpers.entity import Entity
from framework.helpers.exception_utils import RestError

class TestEntity:
    @pytest.fixture
    def entity(self):
        ip = "192.168.0.1"
        username = "admin"
        password = "password"
        resource_type = "vm"
        session = MagicMock()
        return Entity(ip=ip, username=username, password=password, resource_type=resource_type, session=session)

    def test_create(self, entity):
        """Test the entity creation."""
        test_data = {"name": "New VM"}
        mock_response = MagicMock()  # simulates response from request.post
        mock_response.json.return_value = test_data  # simulates response.json()
        with patch.object(entity.session, 'post', return_value=mock_response) as mock_post:
            response = entity.create(data=test_data)
            mock_post.assert_called_once_with(entity.resource, data=test_data, jsonify=True)
            assert response.json() == test_data

    def test_read_with_uuid(self, entity):
        """Test the read function with a UUID."""
        test_data = {"id": "1", "name": "Test VM"}
        mock_response = MagicMock()
        mock_response.json.return_value = test_data

        # get method
        with patch.object(entity.session, 'get', return_value=mock_response) as mock_get:
            entity.proxy_cluster_uuid = None
            response = entity.read(uuid="1")
            mock_get.assert_called_once_with(entity.resource + "/1")
            assert response.json() == test_data

        # Test POST method
        with patch.object(entity.session, 'post', return_value=mock_response) as mock_post:
            response = entity.read(uuid="test_uuid", method="POST", data={"key": "value"})
            mock_post.assert_called_once_with(entity.resource + "/test_uuid", data={"key": "value"})
            assert response.json() == test_data

        # Test invalid method
        with pytest.raises(TypeError):
            entity.read(uuid="test_uuid", method="INVALID")

    def test_update(self, entity):
        """Test updating an entity."""
        test_data = {"name": "Updated VM"}
        mock_response = MagicMock()
        mock_response.json.return_value = test_data

        with patch.object(entity.session, 'put', return_value=mock_response) as mock_put:
            response = entity.update(data=test_data, method="PUT")
            mock_put.assert_called_once_with(entity.resource, data=test_data)
            assert response.json() == test_data

        # Test PATCH method
        with patch.object(entity.session, 'patch', return_value=mock_response) as mock_patch:
            response = entity.update(data={"key": "value"}, method="PATCH")
            mock_patch.assert_called_once_with(entity.resource, data={"key": "value"})
            assert response.json() == test_data

        # Test invalid method
        with pytest.raises(TypeError):
            entity.update(data={"key": "value"}, method="INVALID")

    def test_delete(self, entity):
        """Test deleting an entity."""
        with patch.object(entity.session, 'delete', return_value=MagicMock(status_code=204)) as mock_delete:
            endpoint = "1"
            expected_url = f"{entity.resource.rstrip('/')}/{endpoint}"
            response = entity.delete(endpoint=endpoint)
            mock_delete.assert_called_once_with(expected_url)
            assert response.status_code == 204

        # Test DELETE method with exception
        with patch.object(entity.session, 'delete', side_effect=Exception('Test exception')) as mock_delete:
            with pytest.raises(Exception) as e_info:
                entity.delete()
            assert str(e_info.value) == 'Test exception'

    def test_list_with_filters(self, entity):
        """Test listing entities with custom filters."""
        test_entities = {"entities": [{"status": "active"}, {"status": "inactive"}]}
        filtered_entities = [{"status": "active"}]
        custom_filters = {"status": "active"}
        mock_response = MagicMock()
        mock_response.json.return_value = test_entities

        with patch.object(entity.session, 'post', return_value=mock_response) as mock_post:
            response = entity.list(custom_filters=custom_filters)
            mock_post.assert_called_once_with(entity.resource + "/list", data=None)
            processed_response = [entity for entity in test_entities['entities'] if entity['status'] == custom_filters['status']]
            assert processed_response == filtered_entities

    def test_upload_file(self, entity, mocker):
        """Test file upload."""
        test_response = {"message": "File uploaded"}
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = test_response
        mocker.patch('builtins.open', mocker.mock_open(read_data="data"))
        mocker.patch.object(entity.session, 'post', return_value=mock_response)
        response = entity.upload(source='/file.json', data={'key': 'value'})
        entity.session.post.assert_called_once()
        assert response.json() == test_response

    def test_read_server_error(self, entity):
        with patch.object(entity.session, 'get', side_effect=Exception("Server error")):
            with pytest.raises(Exception, match="Server error"):
                entity.read(endpoint="/api/nutanix/v2.0/test")

    def test_create_server_error(self, entity):
        with patch.object(entity.session, 'post', side_effect=Exception("Server error")):
            with pytest.raises(Exception, match="Server error"):
                entity.create(endpoint="/api/nutanix/v2.0/test", data={"name": "test"})

    def test_update_server_error(self, entity):
        with patch.object(entity.session, 'put', side_effect=Exception("Server error")):
            with pytest.raises(Exception, match="Server error"):
                entity.update(endpoint="/api/nutanix/v2.0/test", data={"name": "test"})

    def test_get_spec(self, mocker, entity):
        """Test the get_spec method."""
        old_spec = {"name": "Old Spec"}
        params = {
            "param1": {"config1": "value1"},
            "param2": {"config2": "value2"}
        }

        # Mock build_spec_methods
        mock_build_specs = mocker.patch.object(entity, 'build_spec_methods')
        mock_build_spec_method = MagicMock()
        mock_build_specs.get.return_value=mock_build_spec_method
        mock_build_spec_method.return_value = (old_spec, None)

        # Test with valid params
        spec, error = entity.get_spec(old_spec=old_spec, params=params)
        assert spec == old_spec
        assert error is None
        mock_build_specs.get.assert_any_call("param1")
        mock_build_spec_method.assert_called_with(old_spec, params["param2"])

        # Test with error in build_spec_method
        mock_build_spec_method.return_value = (None, "Error in build_spec_method")
        

        spec, error = entity.get_spec(old_spec=old_spec, params=params)
        assert spec is None
        assert error == "Error in build_spec_method"
        mock_build_specs.get.assert_any_call("param1")


    def test_build_headers(self):
        """Test the _build_headers static method."""
        module = MagicMock()
        module.params = {
            "nutanix_username": "admin",
            "nutanix_password": "password"
        }
        additional_headers = {"Custom-Header": "CustomValue"}

        expected_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Custom-Header": "CustomValue",
            "Authorization": "Basic YWRtaW46cGFzc3dvcmQ="
        }

        headers = Entity._build_headers(module, additional_headers)
        assert headers == expected_headers

        # Test without additional headers
        expected_headers.pop("Custom-Header")
        headers = Entity._build_headers(module, None)
        assert headers == expected_headers

        # Test without username and password
        module.params = {}
        expected_headers.pop("Authorization")
        headers = Entity._build_headers(module, None)
        assert headers == expected_headers

    def test_build_url_with_query(self):
        """Test the _build_url_with_query static method."""
        url = "https://example.com/api/resource"
        query = {"param1": "value1", "param2": "value2"}

        expected_url = "https://example.com/api/resource?param1=value1&param2=value2"
        result_url = Entity._build_url_with_query(url, query)
        assert result_url == expected_url

        # Test with existing query parameters in the URL
        url_with_existing_query = "https://example.com/api/resource?existing_param=existing_value"
        expected_url_with_existing_query = "https://example.com/api/resource?existing_param=existing_value&param1=value1&param2=value2"
        result_url_with_existing_query = Entity._build_url_with_query(url_with_existing_query, query)
        assert result_url_with_existing_query == expected_url_with_existing_query

        # Test with empty query dictionary
        empty_query = {}
        expected_url_with_empty_query = "https://example.com/api/resource?existing_param=existing_value"
        result_url_with_empty_query = Entity._build_url_with_query(url_with_existing_query, empty_query)
        assert result_url_with_empty_query == expected_url_with_empty_query

        # Test with URL that already has some of the same query parameters
        url_with_same_query = "https://example.com/api/resource?param1=old_value"
        expected_url_with_same_query = "https://example.com/api/resource?param1=value1&param2=value2"
        result_url_with_same_query = Entity._build_url_with_query(url_with_same_query, query)
        assert result_url_with_same_query == expected_url_with_same_query




                
    