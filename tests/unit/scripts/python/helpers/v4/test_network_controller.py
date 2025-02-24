import pytest
from unittest.mock import MagicMock
from framework.scripts.python.helpers.v4.network_controller import NetworkController
from unittest.mock import MagicMock, patch

class TestNetworkController:
    @pytest.fixture
    def network_controller(self):
        return NetworkController()

    def test_network_controller_init(self, network_controller):
        assert network_controller.kind == "network-controller"
        
    def test_enable_network_controller(self, mocker, network_controller):
        mock_create = mocker.patch('ntnx_networking_py_client.NetworkControllersApi.create_network_controller')
        mock_response = MagicMock()
        mock_create.return_value = mock_response

        response = network_controller.enable_network_controller()

        mock_create.assert_called_once()
        assert response == mock_response

    def test_disable_network_controller(self, mocker, network_controller):
        mock_delete = mocker.patch('ntnx_networking_py_client.NetworkControllersApi.delete_network_controller_by_id')
        mock_list = mocker.patch('ntnx_networking_py_client.NetworkControllersApi.list_network_controllers')
        mock_list_response = MagicMock()
        mock_list_response.data = [MagicMock(ext_id='test_id')]
        mock_list.return_value = mock_list_response

        mock_delete_response = MagicMock()
        mock_delete.return_value = mock_delete_response

        response = network_controller.disable_network_controller()

        mock_list.assert_called_once()
        mock_delete.assert_called_once_with('test_id')
        assert response == mock_delete_response

    def test_get_network_controller_status(self, mocker, network_controller):
        mock_list = mocker.patch('ntnx_networking_py_client.NetworkControllersApi.list_network_controllers')
        mock_list_response = MagicMock()
        mock_list_response.data = [MagicMock(controller_status='UP')]
        mock_list.return_value = mock_list_response

        status = network_controller.get_network_controller_status()

        mock_list.assert_called_once()
        assert status is True

        mock_list_response.data[0].controller_status = 'DOWN'
        status = network_controller.get_network_controller_status()

        assert status is False

