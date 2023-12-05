from copy import deepcopy
from framework.helpers.rest_utils import RestAPIUtil
from .foundation_central import FoundationCentral

__metaclass__ = type


class ImagedNode(FoundationCentral):
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
    def node_details_by_block_serial(self, block_serials: list, node_state: str = "STATE_AVAILABLE"):
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
