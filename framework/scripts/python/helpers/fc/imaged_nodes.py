from copy import deepcopy
from typing import List, Optional
from framework.helpers.rest_utils import RestAPIUtil
from ..fc_entity import FcEntity

__metaclass__ = type


class ImagedNode(FcEntity):
    entity_type = "imaged_nodes"

    def __init__(self, session: RestAPIUtil):
        self.resource_type = "/imaged_nodes"
        super(ImagedNode, self).__init__(session, self.resource_type)
        self.build_spec_methods = {"filters": self._build_spec_filters}

    def _build_spec_filters(self, payload, value):
        payload["filters"] = value
        return payload, None

    def _get_default_spec(self):
        return deepcopy({"filters": {"node_state": ""}})

    # Helper functions
    def node_details_by_block_serial(self, block_serials: List, node_state: str = "STATE_AVAILABLE"):
        spec = self._get_default_spec()
        spec["filters"]["node_state"] = node_state
        resp = self.list(data=spec)
        node_list = []
        for node in resp:
            if node["block_serial"] in block_serials:
                node_list.append(node)
        return node_list, None

    # Helper function
    def node_details(self, node_state: str = "STATE_AVAILABLE"):
        spec = self._get_default_spec()
        spec["filters"]["node_state"] = node_state
        resp = self.list(data=spec)
        if not resp:
            return None, "No available nodes registered to Foundation Central."
        return resp, None

    # Helper function
    def node_details_by_node_serial(self, node_serial_list: List, fc_available_node_list: Optional[List] = None):
        """Fetch Node details based on node serial list

        Args:
            node_serial_list (list): List of node serials to filter from available nodes
            fc_available_node_list (List, Optional): List of available node in Foundation Central

        Returns:
            List: List of node details for the given node serials
        """
        node_details = {}
        if not fc_available_node_list:
            fc_available_node_list = self.node_details()
        for node in fc_available_node_list:
            if node["node_serial"] in node_serial_list:
                node_details[node["node_serial"]] = node
        return node_details
