from copy import deepcopy
from typing import Optional, List, Dict
from framework.helpers.v4_api_client import ApiClientV4

import ntnx_networking_py_client



class NetworkController:
    kind = "network-controller"

    def __init__(self, v4_api_util: ApiClientV4):
        client = v4_api_util.get_api_client("network")
        self.network_controllers_api = ntnx_networking_py_client.NetworkControllersApi(
            api_client=client
            )

    def enable_network_controller(self):
        networkController = ntnx_networking_py_client.NetworkController()
        api_response = self.network_controllers_api.create_network_controller(
            body=networkController)
        return api_response

    def disable_network_controller(self):
        resp = self.network_controllers_api.list_network_controllers()
        extId = resp.data[0].ext_id
        api_response = self.network_controllers_api.delete_network_controller_by_id(extId)
        return api_response

    def get_network_controller_status(self) -> bool:
        resp = self.network_controllers_api.list_network_controllers()
        if resp.data:
            if resp.data[0].controller_status == "UP":
                return True
        return False
