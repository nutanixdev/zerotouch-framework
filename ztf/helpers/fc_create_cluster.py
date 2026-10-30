"""
FC Create Cluster Helper

Creates a cluster from nodes already onboarded to Foundation Central 2.x:

    POST /api/v1/foundation-central/internal/nodes/create-cluster

Nodes are addressed by their FC node extId -- the same extId returned by
``GET /api/lifecycle/v4.x/config/nodes`` and used by the fc_node entity --
not by serial number.

The call is asynchronous: FC returns a task extId, which this helper polls
until the cluster-create task finishes, then returns the created cluster's
extId so dependent resources can reference ``{resource.extId}``.

If every listed node already carries the same ``clusterExtId`` (GET
``/api/lifecycle/v4.x/config/nodes/{extId}``), create is skipped and that
id is returned so post-cluster ops can still interpolate
``{resource.extId}``.

FC rejects the POST unless it carries an ``NTNX-Request-Id`` header holding
a valid UUID (server-side: "Failed to create cluster create task: Invalid
NTNX-Request-Id format, must be a valid UUID", surfaced to the client only
as a generic FC-10001 500).  A fresh UUID is generated on every create call,
so it satisfies the header requirement but does *not* act as an idempotence
token across retries -- a retried create looks like a new request to FC.
Idempotence comes instead from the already-clustered check below.  Pass an
explicit ``request_id`` in the body to pin the token yourself.

For the legacy Foundation Central v1 API (``/api/fc/v1/imaged_clusters``,
which addresses nodes by serial) use ``FcClusterHelper`` instead.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ztf.helpers.pe_entity_v1 import PeEntityV1
from ztf.helpers.utils.rest_utils import RestAPIUtil
from ztf.utils.utils import get_logger

FC_CREATE_CLUSTER_PATH = "api/v1/foundation-central/internal/nodes/create-cluster"

#: Task endpoint candidates, tried in order.  The minor version served
#: varies by PC build, and an unsupported one 404s at the routing layer.
FC_TASK_PATHS = (
    "api/prism/v4.4/config/tasks",
    "api/prism/v4.3/config/tasks",
    "api/prism/v4.0/config/tasks",
)

#: Lifecycle node GET candidates used to recover the new cluster's extId
#: from a node after create-cluster leaves the task's entitiesAffected empty.
FC_NODE_PATHS = (
    "api/lifecycle/v4.4/config/nodes",
    "api/lifecycle/v4.3/config/nodes",
    "api/lifecycle/v4.1/config/nodes",
    "api/lifecycle/v4.0/config/nodes",
)

#: Clustermgmt list candidates used as a last-resort lookup by cluster name.
FC_CLUSTER_PATHS = (
    "api/clustermgmt/v4.3/config/clusters",
    "api/clustermgmt/v4.1/config/clusters",
    "api/clustermgmt/v4.0/config/clusters",
)

_TERMINAL_FAILURE_STATES = {"FAILED", "ABORTED", "CANCELED", "CANCELLED"}

_DEFAULT_TIMEOUT_SECONDS = 3600
_DEFAULT_POLL_INTERVAL_SECONDS = 30


class FcCreateClusterHelper(PeEntityV1):
    """Helper for FC 2.x cluster creation from onboarded nodes."""

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
        self._task_path: str | None = None
        self._node_path: str | None = None
        self._cluster_path: str | None = None
        super().__init__(session=session, proxy_cluster_uuid=proxy_cluster_uuid)

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_nodes(nodes: Any) -> list[dict[str, str]]:
        """Coerce the ``nodes`` input into the API's ``[{"extId": ...}]`` shape.

        Accepts a bare extId string, a list of extId strings, or a list of
        dicts already carrying ``extId`` (or ``ext_id``).
        """
        if isinstance(nodes, str):
            nodes = [nodes]
        if not isinstance(nodes, list):
            raise ValueError("'nodes' must be a string or a list")

        normalized: list[dict[str, str]] = []
        for node in nodes:
            ext_id: Any
            if isinstance(node, str):
                ext_id = node
            elif isinstance(node, dict):
                ext_id = node.get("extId") or node.get("ext_id")
            else:
                raise ValueError(f"Unsupported node entry: {node!r}")

            if not ext_id:
                raise ValueError(f"Node entry is missing an extId: {node!r}")
            normalized.append({"extId": str(ext_id)})

        return normalized

    @staticmethod
    def _join_servers(value: Any) -> str:
        """Render a DNS/NTP server list as the comma-separated string FC expects."""
        if isinstance(value, list | tuple):
            return ",".join(str(v) for v in value)
        return str(value)

    def _build_payload(self, entity_data: dict[str, Any]) -> dict[str, Any]:
        """Map the YAML body onto the create-cluster request payload."""
        cluster_name = entity_data.get("cluster_name") or entity_data.get("clusterName")
        if not cluster_name:
            raise ValueError("entity_data must contain 'cluster_name'")

        nodes = entity_data.get("nodes")
        if not nodes:
            raise ValueError("entity_data must contain 'nodes'")

        payload: dict[str, Any] = {
            "nodes": self._normalize_nodes(nodes),
            "clusterName": cluster_name,
        }

        # snake_case is the ZTF convention for helper bodies; the camelCase
        # spelling is accepted too so the API payload can be pasted verbatim.
        optional_fields = (
            ("timezone", "timezone"),
            ("external_ip", "externalIp"),
            ("cluster_fault_tolerance", "clusterFaultTolerance"),
            ("cvm_dns_servers", "cvmDnsServers"),
            ("cvm_ntp_servers", "cvmNtpServers"),
            ("hypervisor_ntp_servers", "hypervisorNtpServers"),
        )
        server_fields = {"cvmDnsServers", "cvmNtpServers", "hypervisorNtpServers"}

        for snake_key, api_key in optional_fields:
            value = entity_data.get(snake_key)
            if value is None:
                value = entity_data.get(api_key)
            if value is None:
                continue
            payload[api_key] = (
                self._join_servers(value) if api_key in server_fields else value
            )

        return payload

    @staticmethod
    def _build_headers(entity_data: dict[str, Any]) -> dict[str, str]:
        """Build request headers, including the mandatory NTNX-Request-Id.

        A body-supplied ``request_id`` is validated as a UUID and used as-is;
        otherwise a fresh UUID is minted. Because each call mints its own, the
        header is not an idempotence token across retries -- see the module
        docstring.

        ``RestAPIUtil`` replaces its default headers wholesale when any are
        passed, so Content-Type has to be restated here.
        """
        request_id = entity_data.get("request_id")
        if request_id:
            try:
                uuid.UUID(str(request_id))
            except ValueError as e:
                raise ValueError(
                    f"'request_id' must be a valid UUID, got {request_id!r}"
                ) from e
        else:
            request_id = str(uuid.uuid4())

        return {
            "Content-Type": "application/json",
            "NTNX-Request-Id": str(request_id),
        }

    # ------------------------------------------------------------------
    # Task polling
    # ------------------------------------------------------------------

    def _get_task(self, task_ext_id: str) -> dict[str, Any]:
        """Fetch a v4 task, discovering the served task-API version once."""
        candidates = [self._task_path] if self._task_path else list(FC_TASK_PATHS)
        last_error: Exception | None = None

        for path in candidates:
            try:
                resp = self.session.get(f"{path}/{task_ext_id}")
            except Exception as e:
                last_error = e
                continue
            self._task_path = path
            return self._unwrap_data(resp)

        raise RuntimeError(
            f"Unable to read task {task_ext_id} from any of {FC_TASK_PATHS}: "
            f"{last_error}"
        )

    @staticmethod
    def _unwrap_data(resp: Any) -> dict[str, Any]:
        """Return the inner ``data`` object when the GET wrapped one."""
        if isinstance(resp, dict):
            data = resp.get("data")
            return data if isinstance(data, dict) else resp
        return {}

    @staticmethod
    def _ext_id_from_ref(item: dict[str, Any]) -> str | None:
        for key in ("extId", "ext_id", "uuid"):
            value = item.get(key)
            if value:
                return str(value)
        return None

    @staticmethod
    def _cluster_ext_id_from_task(task: dict[str, Any]) -> str | None:
        """Pick the created cluster's extId out of a completed task.

        FC create-cluster tasks often leave ``entitiesAffected`` empty
        (same pattern as CreatePatchedImageTask) and only surface the
        real id via a ``completionDetails`` ``{name: "..._uuid",
        value: "<uuid>"}`` pair. Only an affected entity whose ``rel``
        names a cluster is accepted; a node (or other) extId must not be
        stored as the cluster id. The task's own ``extId`` is the Ergon
        task id (prefixed ``ZXJnb24=:``, i.e. ``ergon:``) and must not
        be stored as the cluster extId.
        """
        entities = task.get("entitiesAffected") or task.get("entities_affected") or []
        if isinstance(entities, dict):
            entities = [entities]
        if isinstance(entities, list):
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                rel = str(entity.get("rel", "")).lower()
                ext_id = FcCreateClusterHelper._ext_id_from_ref(entity)
                if "cluster" in rel and ext_id:
                    return ext_id

        details = task.get("completionDetails") or task.get("completion_details") or []
        if isinstance(details, dict):
            details = [details]
        if not isinstance(details, list):
            return None

        fallback_uuid = None
        for item in details:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("key") or "").lower()
            value = item.get("value")
            if not value or str(value) in {"N/A", "n/a"}:
                continue
            if "cluster" in name and (
                "uuid" in name or "extid" in name or name.endswith("_id")
            ):
                return str(value)
            if name.endswith("_uuid") and fallback_uuid is None:
                fallback_uuid = str(value)
        return fallback_uuid

    def _wait_for_task(
        self, task_ext_id: str, timeout: int, interval: int
    ) -> str | None:
        """Poll until the cluster-create task settles.

        Returns the created cluster's extId, or ``None`` if the task
        succeeded without reporting an affected entity.
        """
        deadline = time.monotonic() + timeout
        last_status = None

        while time.monotonic() < deadline:
            task = self._get_task(task_ext_id)
            status = task.get("status")

            if status != last_status:
                self.logger.info(f"Cluster-create task {task_ext_id}: {status}")
                last_status = status

            if status == "SUCCEEDED":
                cluster_ext_id = self._cluster_ext_id_from_task(task)
                if not cluster_ext_id:
                    self.logger.debug(
                        "Cluster-create task %s succeeded without a cluster "
                        "extId in entitiesAffected/completionDetails: keys=%s",
                        task_ext_id,
                        sorted(task.keys()),
                    )
                return cluster_ext_id
            if status in _TERMINAL_FAILURE_STATES:
                raise RuntimeError(
                    f"Cluster-create task {task_ext_id} {status}: "
                    f"{task.get('errorMessages') or task.get('legacyErrorMessage')}"
                )

            time.sleep(interval)

        raise RuntimeError(
            f"Cluster-create task {task_ext_id} did not finish within {timeout}s"
        )

    def _poll_settings(self, entity_data: dict[str, Any]) -> tuple[int, int]:
        """Resolve poll timeout/interval from the body, then global config."""
        config = self.data.get("config", {}) if isinstance(self.data, dict) else {}
        timeout = (
            entity_data.get("timeout_seconds")
            or config.get("task_timeout_seconds")
            or _DEFAULT_TIMEOUT_SECONDS
        )
        interval = (
            entity_data.get("poll_interval_seconds")
            or config.get("task_check_interval_seconds")
            or _DEFAULT_POLL_INTERVAL_SECONDS
        )
        return int(timeout), int(interval)

    def _cluster_ext_id_from_node(self, node_ext_id: str) -> str | None:
        """Read ``clusterExtId`` off a lifecycle node, if the node is clustered."""
        candidates = [self._node_path] if self._node_path else list(FC_NODE_PATHS)
        for path in candidates:
            if not path:
                continue
            try:
                resp = self.session.get(f"{path}/{node_ext_id}")
            except Exception as e:
                self.logger.debug(f"Node GET {path}/{node_ext_id} failed: {e}")
                continue
            self._node_path = path
            node = self._unwrap_data(resp)
            cluster_ext_id = (
                node.get("clusterExtId")
                or node.get("cluster_ext_id")
                or (
                    node.get("cluster", {}).get("extId")
                    if isinstance(node.get("cluster"), dict)
                    else None
                )
            )
            return str(cluster_ext_id) if cluster_ext_id else None
        return None

    def _cluster_ext_id_by_name(self, cluster_name: str) -> str | None:
        """List clustermgmt clusters filtered by name; return the first extId."""
        odata_name = str(cluster_name).replace("'", "''")
        candidates = (
            [self._cluster_path] if self._cluster_path else list(FC_CLUSTER_PATHS)
        )
        for path in candidates:
            if not path:
                continue
            try:
                resp = self.session.get(
                    path, params={"$filter": f"name eq '{odata_name}'"}
                )
            except Exception as e:
                self.logger.debug(f"Cluster list {path} failed: {e}")
                continue
            self._cluster_path = path
            data = resp.get("data") if isinstance(resp, dict) else resp
            clusters = data if isinstance(data, list) else []
            for cluster in clusters:
                if not isinstance(cluster, dict):
                    continue
                name = cluster.get("name") or cluster.get("clusterName")
                ext_id = self._ext_id_from_ref(cluster)
                if ext_id and (name is None or str(name) == str(cluster_name)):
                    return ext_id
            return None
        return None

    def _existing_cluster_ext_id(self, nodes: list[dict[str, str]]) -> str | None:
        """Return the cluster extId when every node is already in the same cluster.

        Used to skip create-cluster on an already-clustered node so dependents
        (post-cluster ops) still receive a real ``{resource.extId}``.

        Raises ``ValueError`` when nodes disagree: some clustered and some
        not, or more than one distinct ``clusterExtId``.
        """
        found: list[str | None] = []
        for node in nodes:
            node_ext_id = node.get("extId") if isinstance(node, dict) else None
            if not node_ext_id:
                continue
            found.append(self._cluster_ext_id_from_node(str(node_ext_id)))

        clustered = {ext_id for ext_id in found if ext_id}
        if not clustered:
            return None
        if len(clustered) > 1:
            raise ValueError(
                f"Nodes belong to different clusters ({sorted(clustered)}); "
                "cannot skip create-cluster"
            )
        if any(ext_id is None for ext_id in found):
            clustered_id = next(iter(clustered))
            raise ValueError(
                f"Some nodes are already in cluster {clustered_id} and others "
                "are not; cannot skip create-cluster"
            )
        return next(iter(clustered))

    def _resolve_cluster_ext_id(
        self, cluster_name: str, nodes: list[dict[str, str]]
    ) -> str | None:
        """Recover the created cluster's extId when the task omitted it."""
        for node in nodes:
            node_ext_id = node.get("extId") if isinstance(node, dict) else None
            if not node_ext_id:
                continue
            cluster_ext_id = self._cluster_ext_id_from_node(str(node_ext_id))
            if cluster_ext_id:
                self.logger.info(
                    f"Resolved cluster extId {cluster_ext_id} from node {node_ext_id}"
                )
                return cluster_ext_id

        cluster_ext_id = self._cluster_ext_id_by_name(cluster_name)
        if cluster_ext_id:
            self.logger.info(
                f"Resolved cluster extId {cluster_ext_id} by name {cluster_name!r}"
            )
        return cluster_ext_id

    # ------------------------------------------------------------------
    # Entity handler interface
    # ------------------------------------------------------------------

    def create_entity(self, entity_data: dict[str, Any]) -> str:
        """
        Create a cluster from onboarded FC nodes.

        Expected entity_data:
            cluster_name: str (required)
            nodes: list of node extIds, or of {"extId": "..."} (required)
            timezone: str (optional, e.g. "UTC")
            external_ip: str (optional, cluster VIP)
            cluster_fault_tolerance: str (optional, e.g. "CFT_1N_AND_1D")
            cvm_dns_servers: str or list (optional)
            cvm_ntp_servers: str or list (optional)
            hypervisor_ntp_servers: str or list (optional)
            wait_for_completion: bool (optional, default True)
            timeout_seconds / poll_interval_seconds: int (optional)
            request_id: str (optional, UUID; auto-generated when omitted)

        If every node already has the same ``clusterExtId``, the POST is
        skipped and that id is returned (so ``{resource.extId}`` still
        resolves for post-cluster ops).

        :return: created (or already-existing) cluster ext_id, or the
                 task ext_id when waiting is disabled
        """
        payload = self._build_payload(entity_data)
        cluster_name = payload["clusterName"]
        nodes = payload.get("nodes") or []

        existing = self._existing_cluster_ext_id(nodes)
        if existing:
            self.logger.info(
                f"FC cluster create skipped for {cluster_name}: node(s) "
                f"already clustered as {existing}"
            )
            return existing

        headers = self._build_headers(entity_data)

        self.logger.debug(f"FC create-cluster request id: {headers['NTNX-Request-Id']}")

        try:
            resp = self.session.post(
                FC_CREATE_CLUSTER_PATH, headers=headers, data=payload
            )
        except Exception as e:
            self.logger.error(f"Failed to create FC cluster {cluster_name}: {e}")
            raise

        if not resp:
            raise RuntimeError("Empty response from FC create cluster")

        task_ext_id = None
        if isinstance(resp, dict):
            data = resp.get("data")
            source = data if isinstance(data, dict) else resp
            task_ext_id = source.get("extId") or source.get("taskExtId")

        if not task_ext_id:
            raise RuntimeError(f"No task extId in FC create-cluster response: {resp}")

        self.logger.info(
            f"FC cluster create submitted for {cluster_name}: task {task_ext_id}"
        )

        if entity_data.get("wait_for_completion", True) is False:
            return str(task_ext_id)

        timeout, interval = self._poll_settings(entity_data)
        cluster_ext_id = self._wait_for_task(str(task_ext_id), timeout, interval)

        if not cluster_ext_id:
            self.logger.warning(
                f"Cluster-create task {task_ext_id} succeeded but reported no "
                "affected entity; looking up the cluster by node and name"
            )
            cluster_ext_id = self._resolve_cluster_ext_id(
                cluster_name, payload.get("nodes") or []
            )

        if not cluster_ext_id:
            raise RuntimeError(
                f"Cluster-create task {task_ext_id} succeeded but the created "
                f"cluster extId could not be determined for {cluster_name!r}. "
                "The task had no entitiesAffected/completionDetails and lookup "
                "by node/name also failed. The cluster may still exist; do "
                "not retry create blindly."
            )

        self.logger.info(f"FC cluster {cluster_name} created: {cluster_ext_id}")
        return cluster_ext_id

    def update_entity(self, ext_id: str, entity_data: dict[str, Any]) -> str:
        raise NotImplementedError("Update for FC created cluster is not implemented")

    def delete_entity(self, ext_id: str) -> bool:
        raise NotImplementedError("Delete for FC created cluster is not implemented")

    def list_entities(
        self, custom_filter: dict | None = None, **kwargs
    ) -> list[dict[str, Any]]:
        """Not supported: create-cluster is an action endpoint with no listing.

        Returning an empty list (rather than raising) keeps ZTF's refresh
        and plan paths working; state for this resource is authoritative.
        """
        return []

    def get_entity_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        """Not supported: see :meth:`list_entities`.

        ZTF falls back to the configured body when this returns ``None``,
        so state stays equal to config and repeat applies are no-ops.
        """
        return None
