"""
FC Imaging Helper

Backport of zero-touch-ee imaging_only.py into the v4 entity_handler interface.
Resolves node serials from FC, merges per-node overrides, sets image_now,
and submits a deployment via Foundation Central.

Supports two modes:
  1. Imaging only  (skip_cluster_creation: true)  -- default
  2. Image + cluster creation (skip_cluster_creation: false)

For cluster creation without imaging, use FcClusterHelper instead.

Connects to PC (https://PC:9440) and uses the FC API.
"""

from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

FC_IMAGED_CLUSTERS_PATH = "api/fc/v1/imaged_clusters"
FC_IMAGED_NODES_PATH = "api/fc/v1/imaged_nodes"


class FcImagingHelper(PeEntityV1):
    """
    Helper for FC imaging deployments (imaging only, or image + cluster creation).
    For cluster creation from already-imaged nodes, use FcClusterHelper.
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
        """List imaged nodes from FC. FC uses POST for listing."""
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

    _VALID_NODE_ROLES = {"hyperconverged", "storage", "compute"}

    @staticmethod
    def _sanitize_node_records(resolved_nodes: list[dict]) -> None:
        """Clean up node records before submitting to FC.

        1. Strip IPMI fields — FC does not use IPMI for imaging, but
           Foundation's validate_and_correct_network_addresses() still
           validates them.  All three fields must be removed together
           (FC enforces all-or-nothing).

        2. Fix invalid node_role — FC discovers nodes with
           node_role="unsupported_node" but rejects that value on
           the imaged_clusters POST (must be one of hyperconverged,
           storage, compute).  Default to "hyperconverged".
        """
        for n in resolved_nodes:
            n.pop("ipmi_ip", None)
            n.pop("ipmi_gateway", None)
            n.pop("ipmi_netmask", None)

            role = n.get("node_role", "")
            if role not in FcImagingHelper._VALID_NODE_ROLES:
                n["node_role"] = "hyperconverged"

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Submit an FC imaging deployment.

        Mirrors the original zero-touch-ee Imaging class:
        1. Resolve node serials from FC (full node records)
        2. Merge per-node overrides from input
        3. Set image_now=True on each node
        4. POST to FC imaged_clusters endpoint

        Node records are sanitized before submission:
        - IPMI fields stripped (FC doesn't use IPMI for imaging)
        - Invalid node_role defaulted to "hyperconverged"
        """
        cluster_name = entity_data.get("cluster_name", "fc_imaging")
        nodes_list = entity_data.get("nodes_list", [])
        if not nodes_list:
            raise ValueError("entity_data must contain 'nodes_list'")

        skip_cluster = entity_data.get("skip_cluster_creation", True)

        if skip_cluster and len(nodes_list) < 2:
            raise ValueError(
                "FC imaging-only mode requires at least 2 nodes. "
                "Provide at least 2 nodes in nodes_list, or set "
                "skip_cluster_creation: false to image and create a cluster."
            )

        mode = "imaging_only" if skip_cluster else "image_and_cluster"
        self.logger.info(f"FC deployment mode: {mode} for {cluster_name}")

        node_serial_list = [n["node_serial"] for n in nodes_list if "node_serial" in n]
        if node_serial_list:
            existing = self._node_details_by_serial(node_serial_list)
            if len(existing) < len(node_serial_list):
                missing = set(node_serial_list) - set(existing.keys())
                raise ValueError(f"Node serials {missing} not available in FC.")

            unavailable = [
                s for s, n in existing.items() if not n.get("available", True)
            ]
            if unavailable:
                raise ValueError(
                    f"Nodes {unavailable} are not available in FC. "
                    "Check node state in Foundation Central before retrying."
                )

            for node in nodes_list:
                serial = node.get("node_serial")
                if serial and serial in existing:
                    for key, value in node.items():
                        existing[serial][key] = value

            for serial in existing:
                existing[serial]["image_now"] = True

            resolved_nodes = [
                existing[n["node_serial"]]
                for n in nodes_list
                if n.get("node_serial") in existing
            ]

            self._sanitize_node_records(resolved_nodes)
        else:
            resolved_nodes = nodes_list
            for n in resolved_nodes:
                n["image_now"] = True

        imaging_params = entity_data.get("imaging_parameters", {})

        payload = {
            "nodes_list": resolved_nodes,
            "skip_cluster_creation": skip_cluster,
        }

        if imaging_params.get("aos_package_url"):
            payload["aos_package_url"] = imaging_params["aos_package_url"]
        if imaging_params.get("aos_package_sha256sum"):
            payload["aos_package_sha256sum"] = imaging_params["aos_package_sha256sum"]
        if imaging_params.get("aos_metadata_url"):
            payload["aos_metadata_url"] = imaging_params["aos_metadata_url"]
        if entity_data.get("hypervisor_isos"):
            payload["hypervisor_isos"] = entity_data["hypervisor_isos"]

        network_settings = entity_data.get("network_settings") or entity_data.get(
            "common_network_settings"
        )
        if network_settings:
            payload["common_network_settings"] = network_settings

        payload["cluster_name"] = cluster_name
        if not skip_cluster:
            payload["cluster_size"] = entity_data.get(
                "cluster_size", len(resolved_nodes)
            )
            if entity_data.get("redundancy_factor") is not None:
                payload["redundancy_factor"] = entity_data["redundancy_factor"]
            if entity_data.get("cluster_external_ip") is not None:
                payload["cluster_external_ip"] = entity_data["cluster_external_ip"]

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
                raise RuntimeError(f"Empty response from FC {mode} deployment")
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
                f"FC {mode} deployment submitted for {cluster_name}: {ext_id}"
            )
            return str(ext_id)
        except Exception as e:
            self.logger.error(
                f"Failed to submit FC {mode} deployment {cluster_name}: {e}"
            )
            raise

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update for FC imaging deployment is not implemented")

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError("Delete for FC imaging deployment is not implemented")

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """List FC imaged clusters (deployments)."""
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
            self.logger.error(f"Failed to list FC deployments: {e}")
            return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Get FC deployment by UUID or name."""
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
            self.logger.error(f"Failed to get FC deployment {ext_id}: {e}")
            return None
