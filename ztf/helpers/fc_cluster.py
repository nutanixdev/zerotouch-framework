"""
FC Cluster Helper

Creates clusters via Foundation Central from nodes that are already imaged
and available in FC. No imaging is performed by this helper.

Connects to PC (https://PC:9440) and uses the FC API.
Implements the entity_handler interface.
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

FC_IMAGED_CLUSTERS_PATH = "api/fc/v1/imaged_clusters"
FC_IMAGED_NODES_PATH = "api/fc/v1/imaged_nodes"


class FcClusterHelper(PeEntityV1):
    """
    Helper for creating clusters from already-imaged nodes via Foundation Central.
    For imaging (with or without cluster creation), use FcImagingHelper instead.
    """

    def __init__(
        self,
        session: RestAPIUtil,
        proxy_cluster_uuid: str | None = None,
        logger=None,
        data: dict | None = None,
    ):
        self.resource_type = "/cluster"
        self.logger = logger if logger else get_logger(__name__)
        self.data = data or {}
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    def _get_imaged_nodes(self) -> list[dict]:
        """List imaged nodes from FC. FC only allows POST for listing."""
        try:
            try:
                resp = self.session.post(FC_IMAGED_NODES_PATH + "/list", data={})
            except Exception:
                resp = self.session.post(FC_IMAGED_NODES_PATH, data={})
            if isinstance(resp, dict) and "imaged_nodes" in resp:
                return resp["imaged_nodes"]
            if isinstance(resp, dict) and "entities" in resp:
                return resp["entities"]
            if isinstance(resp, list):
                return resp
            return []
        except Exception as e:
            self.logger.error(f"Failed to list imaged nodes: {e}")
            raise

    def _node_details_by_serial(self, node_serial_list: list[str]) -> dict[str, dict]:
        """Get node detail dict keyed by node_serial from FC."""
        all_nodes = self._get_imaged_nodes()
        by_serial = {}
        for n in all_nodes:
            if isinstance(n, dict):
                serial = n.get("node_serial") or n.get("serial")
                if serial in node_serial_list:
                    by_serial[serial] = n
        return by_serial

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Create a cluster from already-imaged nodes via FC.

        Expected entity_data:
            cluster_name: str
            nodes_list: list of {"node_serial": "..."} (optional per-node overrides)
            cluster_size: int (optional, default len(nodes_list))
            redundancy_factor: int (optional, default 2)
            cluster_external_ip: str (optional)
            network_settings / common_network_settings: dict (optional)
            timezone: str (optional, e.g. "America/Los_Angeles", "UTC")
            cvm_vlan_id: int (optional, VLAN tag for host-CVM subnet, 1-4093)
            cvm_ram_gb: int (optional, CVM vRAM in GB, min 20)
            rdma_passthrough: bool (optional, passthrough RDMA NICs to CVMs)
            enable_lacp: bool (optional, enable LACP on hypervisor)

        Note: node_role is fetched automatically from FC's imaged nodes API
              and does not need to be specified in the YAML.
              IPMI fields are filtered out for cluster-only creation since
              they are already set during imaging.

        :return: imaged_cluster_uuid or cluster_name as ext_id
        """
        cluster_name = entity_data.get("cluster_name")
        if not cluster_name:
            raise ValueError("entity_data must contain 'cluster_name'")

        nodes_list = entity_data.get("nodes_list", [])
        if not nodes_list:
            raise ValueError("entity_data must contain 'nodes_list'")

        # Fetch node details from FC API to get node_role and other properties
        if isinstance(nodes_list[0], dict) and "node_serial" in nodes_list[0]:
            serials = [n["node_serial"] for n in nodes_list if "node_serial" in n]
            existing = self._node_details_by_serial(serials)
            if len(existing) < len(serials):
                missing = set(serials) - set(existing.keys())
                raise ValueError(
                    f"Not enough imaged nodes in FC for serials: {missing}"
                )

            unavailable = [
                s for s, n in existing.items() if not n.get("available", True)
            ]
            if unavailable:
                raise ValueError(
                    f"Nodes {unavailable} are not available in FC. "
                    "Nodes must be imaged and in STATE_AVAILABLE before "
                    "cluster creation."
                )

            for node in nodes_list:
                serial = node.get("node_serial")
                if serial and serial in existing:
                    # Keep FC's node_role, but allow user to override other fields
                    fc_node = existing[serial]
                    for key, value in node.items():
                        if key != "node_role":  # Don't override node_role from YAML
                            fc_node[key] = value

            ipmi_fields = {
                "ipmi_ip",
                "ipmi_gateway",
                "ipmi_netmask",
                "ipmi_user",
                "ipmi_password",
            }
            nodes_list = [
                {
                    k: v
                    for k, v in existing[n["node_serial"]].items()
                    if k not in ipmi_fields
                }
                for n in nodes_list
                if n.get("node_serial") in existing
            ]

            # Log the node roles fetched from FC
            for node in nodes_list:
                role = node.get("node_role", "unknown")
                serial = node.get("node_serial", "unknown")
                self.logger.info(f"Node {serial} has role: {role} (fetched from FC)")

        payload = {
            "cluster_name": cluster_name,
            "nodes_list": nodes_list,
            "skip_cluster_creation": False,
            "cluster_size": entity_data.get("cluster_size", len(nodes_list)),
            "redundancy_factor": entity_data.get("redundancy_factor", 2),
        }

        if entity_data.get("cluster_external_ip") is not None:
            payload["cluster_external_ip"] = entity_data["cluster_external_ip"]

        # Support both old name (common_network_settings) and new name (network_settings)
        network_settings = entity_data.get("network_settings") or entity_data.get(
            "common_network_settings"
        )
        if network_settings is not None:
            payload["common_network_settings"] = network_settings

        if entity_data.get("timezone") is not None:
            payload["timezone"] = entity_data["timezone"]
        if entity_data.get("cvm_vlan_id") is not None:
            payload["cvm_vlan_id"] = entity_data["cvm_vlan_id"]
        if entity_data.get("cvm_ram_gb") is not None:
            payload["cvm_ram_gb"] = entity_data["cvm_ram_gb"]
        if entity_data.get("rdma_passthrough") is not None:
            payload["rdma_passthrough"] = entity_data["rdma_passthrough"]
        if entity_data.get("enable_lacp") is not None:
            payload["enable_lacp"] = entity_data["enable_lacp"]

        try:
            resp = self.session.post(FC_IMAGED_CLUSTERS_PATH, data=payload)
            if not resp:
                raise RuntimeError("Empty response from FC create cluster")
            ext_id = None
            if isinstance(resp, dict):
                ext_id = (
                    resp.get("imaged_cluster_uuid")
                    or resp.get("cluster_uuid")
                    or resp.get("ext_id")
                    or cluster_name
                )
            if not ext_id:
                ext_id = cluster_name
            self.logger.info(
                f"FC cluster create submitted for {cluster_name}: {ext_id}"
            )
            return str(ext_id)
        except Exception as e:
            self.logger.error(f"Failed to create FC cluster {cluster_name}: {e}")
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update for FC imaged cluster is not implemented")

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError("Delete for FC imaged cluster is not implemented")

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List FC imaged clusters."""
        try:
            try:
                resp = self.session.post(FC_IMAGED_CLUSTERS_PATH + "/list", data={})
            except Exception:
                resp = self.session.post(FC_IMAGED_CLUSTERS_PATH, data={})
            clusters = (
                resp
                if isinstance(resp, list)
                else (resp.get("imaged_clusters") or resp.get("entities") or [])
            )
            entities = []
            for c in clusters:
                if isinstance(c, dict):
                    eid = (
                        c.get("imaged_cluster_uuid")
                        or c.get("ext_id")
                        or c.get("cluster_name")
                    )
                    entities.append(
                        {"cluster_name": c.get("cluster_name"), "extId": eid, **c}
                    )
            if custom_filter and isinstance(custom_filter, dict):
                name = custom_filter.get("cluster_name")
                if name is not None:
                    entities = [e for e in entities if e.get("cluster_name") == name]
            return entities
        except Exception as e:
            self.logger.error(f"Failed to list FC imaged clusters: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get FC imaged cluster by UUID or name."""
        try:
            try:
                resp = self.session.post(FC_IMAGED_CLUSTERS_PATH + "/list", data={})
            except Exception:
                resp = self.session.post(FC_IMAGED_CLUSTERS_PATH, data={})
            clusters = (
                resp
                if isinstance(resp, list)
                else (resp.get("imaged_clusters") or resp.get("entities") or [])
            )
            for c in clusters:
                if isinstance(c, dict) and (
                    c.get("imaged_cluster_uuid") == ext_id
                    or c.get("ext_id") == ext_id
                    or c.get("cluster_name") == ext_id
                ):
                    return {"extId": c.get("imaged_cluster_uuid") or ext_id, **c}
            return None
        except Exception as e:
            self.logger.error(f"Failed to get FC cluster {ext_id}: {e}")
            return None
