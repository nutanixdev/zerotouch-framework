import pytest
from framework.helpers.rest_utils import RestAPIUtil
from framework.scripts.python.helpers.v1.http_proxy import HttpProxy
from framework.scripts.python.helpers.pe_entity_v1 import PeEntityV1
from unittest.mock import MagicMock

class TestHttpProxy:
    @pytest.fixture
    def http_proxy(self):
        self.session = MagicMock(spec=RestAPIUtil)
        self.proxy_cluster_uuid = "test_uuid"
        return HttpProxy(session=self.session, proxy_cluster_uuid=self.proxy_cluster_uuid)
    
    def test_http_proxy_init(self, http_proxy):
        assert http_proxy.resource_type == "/http_proxies"
        assert http_proxy.session == self.session
        assert http_proxy.proxy_cluster_uuid == self.proxy_cluster_uuid
        assert isinstance(http_proxy, HttpProxy)
        assert isinstance(http_proxy, PeEntityV1)
    
    def test_get_payload(self, http_proxy):
        payload = http_proxy.get_payload(
            address="test_address",
            address_value="test_address_value",
            name="test_name",
            password="test_password",
            port="test_port",
            proxy_types=["test_proxy_type"],
            username="test_username"
        )
        assert payload == {
            "address": "test_address",
            "addressValue": "test_address_value",
            "name": "test_name",
            "password": "test_password",
            "port": "test_port",
            "proxyTypes": ["test_proxy_type"],
            "username": "test_username"
        }
    
    def test_create(self, mocker, http_proxy):
        data = {
            "address": "test_address",
            "address_value": "test_address_value",
            "name": "test_name",
            "password": "test_password",
            "port": "test_port",
            "proxy_types": ["test_proxy_type"],
            "username": "test_username"
        }
        mock_create = mocker.patch.object(
            PeEntityV1, "create", return_value={"value": '{"status": "kSucceeded"}'})
        excepted_data = http_proxy.get_payload(**data)
        result = http_proxy.create(**data)
        mock_create.assert_called_once_with(data=excepted_data)
        assert result == {"value": '{"status": "kSucceeded"}'}
    
    def test_update(self, mocker, http_proxy):
        data = {
            "address": "test_address",
            "address_value": "test_address_value",
            "name": "test_name",
            "password": "test_password",
            "port": "test_port",
            "proxy_types": ["test_proxy_type"],
            "username": "test_username"
        }
        mock_update = mocker.patch.object(
            PeEntityV1, "update", return_value={"value": '{"status": "kSucceeded"}'})
        excepted_data = http_proxy.get_payload(**data)
        http_proxy.update(**data)
        mock_update.assert_called_once_with(data=excepted_data)
