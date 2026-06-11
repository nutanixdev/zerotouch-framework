"""Provider: orchestrates resource CRUD, operations, and state management.

Accepts the domain-grouped config format (from ``config_loader``) and
the dict-based state format.
"""

import json
import multiprocessing
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ztf.config.interpolation import (
    InterpolationContext,
    extract_cross_domain_refs,
    extract_resource_refs,
    has_tokens,
    resolve,
)
from ztf.entity_wrapper.entity_handler import DomainEntityHandler
from ztf.entity_wrapper.entity_map import entity_map as entity_metadata_map
from ztf.utils.deep_compare import deep_equal
from ztf.utils.utils import (
    get_logger,
    strip_internal_attributes,
    strip_internal_attributes_for_an_entity,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_parent_kwargs(entity: str, resource: dict[str, Any]) -> dict[str, Any]:
    """Extract parent ID keyword arguments from resource state.

    Checks the ``params`` dict first, then falls back to top-level keys.

    Args:
        entity: Entity name (e.g. ``"rsyslog_server"``).
        resource: Resource dict from state.

    Returns:
        Dict of parent kwargs (e.g. ``{"clusterExtId": "abc-123"}``) or
        empty dict.
    """
    meta = entity_metadata_map.get(entity, {})
    if not isinstance(meta, dict):
        return {}
    parent_id_param = meta.get("parent_id_param")
    if not parent_id_param:
        return {}
    params = resource.get("params", {})
    value = params.get(parent_id_param) or resource.get(parent_id_param)
    if value is None:
        return {}
    return {parent_id_param: value}


def set_entity_thread_name(name: str, func: Callable) -> Callable:
    """Wrap *func* to set the current thread name before execution."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        threading.current_thread().name = name
        return func(*args, **kwargs)

    return wrapper


def _should_ignore_field(field_path: str, ignore_list: list[str]) -> bool:
    """Return ``True`` if *field_path* matches any pattern in *ignore_list*.

    Supports dotted paths and prefix matching:
    ``"config.pulseStatus"`` matches ``"config.pulseStatus.isEnabled"``.
    """
    for pattern in ignore_list:
        if field_path == pattern or field_path.startswith(pattern + "."):
            return True
    return False


def _apply_ignore_changes(
    prev_body: dict[str, Any],
    curr_body: dict[str, Any],
    ignore_list: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Strip fields in *ignore_list* from both bodies before comparison.

    Returns copies — originals are not mutated.
    """
    if not ignore_list:
        return prev_body, curr_body

    def _strip(data: Any, prefix: str = "") -> Any:
        if isinstance(data, dict):
            return {
                k: _strip(v, f"{prefix}{k}." if prefix else f"{k}.")
                for k, v in data.items()
                if not _should_ignore_field(
                    f"{prefix}{k}" if prefix else k, ignore_list
                )
            }
        return data

    return _strip(prev_body), _strip(curr_body)


_NON_CRUD_KEYS = frozenset({"operations", "rules", "depends_on"})


def _is_operations_only(resource_cfg: dict[str, Any]) -> bool:
    """Return True if the resource defines only operations with no CRUD keys."""
    return bool(
        resource_cfg.get("operations") and not (resource_cfg.keys() - _NON_CRUD_KEYS)
    )


def _merge_ignored_fields(
    prev_body: dict[str, Any],
    curr_body: dict[str, Any],
    ignore_list: list[str],
) -> dict[str, Any]:
    """Return a copy of *curr_body* with ignored fields reverted to *prev_body* values.

    For top-level ignored fields the previous value is restored so the
    API update does not overwrite infrastructure state for those fields.
    """
    if not ignore_list or not prev_body:
        return curr_body

    merged = dict(curr_body)
    for key in list(merged):
        if _should_ignore_field(key, ignore_list) and key in prev_body:
            merged[key] = prev_body[key]
    return merged


def _prune_prev_to_curr(prev: Any, curr: Any) -> Any:
    """Prune *prev* to only the keys present in *curr* (recursive).

    Dict keys not declared in *curr* are removed. Lists are preserved, but
    their dict items are pruned using the first element of *curr* as a template.
    """
    if isinstance(prev, dict) and isinstance(curr, dict):
        return {k: _prune_prev_to_curr(prev[k], curr[k]) for k in curr if k in prev}
    if isinstance(prev, list) and isinstance(curr, list) and curr:
        template = curr[0]
        return [_prune_prev_to_curr(item, template) for item in prev]
    return prev


def _compute_field_diff(
    prev_body: dict[str, Any],
    curr_body: dict[str, Any],
) -> dict[str, Any]:
    """Compute a field-level diff between two resource bodies.

    Args:
        prev_body: Previous (state) body.
        curr_body: Current (desired) body.

    Returns:
        Dict with ``added``, ``removed``, and ``changed`` keys.
    """
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}

    all_keys = set(prev_body) | set(curr_body)
    for key in sorted(all_keys):
        in_prev = key in prev_body
        in_curr = key in curr_body
        if in_curr and not in_prev:
            added[key] = curr_body[key]
        elif in_prev and not in_curr:
            removed[key] = prev_body[key]
        elif prev_body[key] != curr_body[key]:
            changed[key] = {"old": prev_body[key], "new": curr_body[key]}

    return {"added": added, "removed": removed, "changed": changed}


class Provider:
    """Orchestrates entity CRUD, operations, and state for all domains.

    Args:
        global_config_data: Base API config from ``global.yml``.
        config: Normalised config from ``config_loader.load_config``.
        previous_state: Previous state dict (new ``domains`` format).
    """

    def __init__(
        self,
        global_config_data: dict[str, Any],
        config: dict[str, Any],
        previous_state: dict[str, Any] | None = None,
    ) -> None:
        self.max_workers: int | None = multiprocessing.cpu_count() + 4

        self.global_config_data = global_config_data
        self.config = config
        self.variables: dict[str, Any] = config.get("variables", {})
        self.default_rules: dict[str, Any] = config.get("defaults", {}).get("rules", {})
        self.functions: dict[str, Any] = config.get("functions", {})
        self.outputs_config: dict[str, Any] = config.get("outputs", {})
        self.previous_state: dict[str, Any] = previous_state or {"domains": {}}

        # domain_name → host mapping
        self.domain_name_to_host: dict[str, str] = {}

        # Keyed by domain_name
        self.domain_global_config_map: dict[str, dict[str, Any]] = {}
        self.domain_entity_resource_map: dict[
            str, dict[str, dict[str, dict[str, Any]]]
        ] = defaultdict(lambda: defaultdict(dict))
        self.domain_resource_name_map: dict[str, set] = defaultdict(set)
        self.domain_data_config: dict[str, dict[str, Any]] = {}
        self.domain_data_cache: dict[str, dict[str, dict[str, Any]]] = {}

        self.previous_domain_entity_resource_map: dict[
            str, dict[str, dict[str, dict[str, Any]]]
        ] = defaultdict(lambda: defaultdict(dict))
        self.previous_domain_resource_name_map: dict[str, set] = defaultdict(set)

        # Cross-domain resource state (populated during apply for interpolation)
        self.domain_resource_state: dict[str, dict[str, dict[str, Any]]] = defaultdict(
            dict
        )

        self.output_skeleton: dict[str, dict[str, Any]] = {"domains": {}}
        self.domain_entity_handler_map: dict[str, DomainEntityHandler] = {}

        # Resource ordering persisted for delete operations (resource-level)
        self.domain_entity_order: dict[str, list[str]] = {}
        self.domain_resource_order: dict[str, list[tuple[str, str]]] = {}

        # Accumulated run results (thread-safe via lock)
        self._run_results: dict[str, list[dict[str, Any]]] = {}
        self._run_results_lock = threading.Lock()
        # Where ``_write_run_results`` persists the audit JSON.  The CLI
        # overrides this to place the file next to the state file; tests
        # and library consumers may point it anywhere.  ``Path`` so the
        # containing directory is easy to derive and create.
        self.run_results_path: Path = Path("ztf_run_results.json")

        # Per-resource partial state (survives interrupts)
        self._partial_results: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        self._partial_results_lock = threading.Lock()
        self._shutdown_requested = threading.Event()

        self._initialize_domain_entity_handlers()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialize_domain_entity_handlers(self) -> None:
        """Build resource maps and entity handlers from config + state."""
        domains = self.config.get("domains", {})
        prev_domains = self.previous_state.get("domains", {})

        # --- Current config ---
        for domain_name, domain_cfg in domains.items():
            host = str(domain_cfg.get("host", domain_name))
            username = domain_cfg.get("username", "")
            password = domain_cfg.get("password", "")

            if not username or not password:
                raise ValueError(
                    f"Domain '{domain_name}' must include 'username' and 'password'."
                )

            self.domain_name_to_host[domain_name] = host

            # Build API config (defensive: ``global_config_data`` is
            # expected to carry a ``config`` sub-dict, but callers that
            # construct Provider in non-standard ways may omit it — use
            # setdefault so we never raise KeyError on the mutation
            # below).
            domain_api_config = deepcopy(self.global_config_data)
            domain_api_config.setdefault("config", {})
            domain_api_config["config"]["host"] = host
            domain_api_config["config"]["username"] = username
            domain_api_config["config"]["password"] = password
            self.domain_global_config_map[domain_name] = domain_api_config

            # Data sources
            self.domain_data_config[domain_name] = domain_cfg.get("data", {})

            # Resources — an empty map is valid (signals "delete everything")
            resources = domain_cfg.get("resources", {})
            if not resources:
                self.domain_resource_name_map[domain_name]  # register empty set
                logger.info(
                    "Domain '%s' has no resources configured. "
                    "Any resources in state will be scheduled for deletion.",
                    domain_name,
                )
            for entity_type, entity_resources in resources.items():
                for resource_name, resource_cfg in entity_resources.items():
                    if (
                        not resource_cfg.get("body")
                        and not resource_cfg.get("ext_id")
                        and not resource_cfg.get("extId")
                        and not resource_cfg.get("operations")
                    ):
                        raise ValueError(
                            f"Resource '{resource_name}' in domain '{domain_name}' "
                            f"must have 'body', 'ext_id'/'extId', or 'operations'."
                        )
                    self.domain_resource_name_map[domain_name].add(resource_name)
                    self.domain_entity_resource_map[domain_name][entity_type][
                        resource_name
                    ] = resource_cfg

        # --- Previous state ---
        for domain_name, domain_state in prev_domains.items():
            host = str(domain_state.get("host", domain_name))
            self.domain_name_to_host.setdefault(domain_name, host)
            prev_resources = domain_state.get("resources", {})
            for entity_type, entity_resources in prev_resources.items():
                for resource_name, resource_data in entity_resources.items():
                    self.previous_domain_resource_name_map[domain_name].add(
                        resource_name
                    )
                    self.previous_domain_entity_resource_map[domain_name][entity_type][
                        resource_name
                    ] = resource_data

            stored_order = domain_state.get("_entity_order", [])
            if stored_order:
                self.domain_entity_order[domain_name] = stored_order

            # Build API config for state-only domains (for delete/refresh)
            if domain_name not in self.domain_global_config_map:
                # Try to find credentials from current config by matching host
                creds_found = False
                for _, dcfg in self.config.get("domains", {}).items():
                    if str(dcfg.get("host", "")) == host:
                        domain_api_config = deepcopy(self.global_config_data)
                        domain_api_config.setdefault("config", {})
                        domain_api_config["config"]["host"] = host
                        domain_api_config["config"]["username"] = dcfg["username"]
                        domain_api_config["config"]["password"] = dcfg["password"]
                        self.domain_global_config_map[domain_name] = domain_api_config
                        creds_found = True
                        break
                if not creds_found:
                    logger.warning(
                        f"Domain '{domain_name}' ({host}) found in state but not in "
                        f"config. Cannot perform delete/refresh without credentials."
                    )

        # --- Create DomainEntityHandler instances ---
        created_hosts: set[str] = set()

        for domain_name in set(self.domain_entity_resource_map) | set(
            self.previous_domain_entity_resource_map
        ):
            api_config = self.domain_global_config_map.get(domain_name)
            if not api_config:
                continue

            host = self.domain_name_to_host.get(domain_name, domain_name)

            # Collect all entity types (current + previous + data sources)
            entity_keys = set(
                self.domain_entity_resource_map.get(domain_name, {}).keys()
            )
            prev_entity_keys = set(
                self.previous_domain_entity_resource_map.get(domain_name, {}).keys()
            )
            data_entity_keys = set(self.domain_data_config.get(domain_name, {}).keys())
            all_entity_keys = entity_keys | prev_entity_keys | data_entity_keys

            if not all_entity_keys:
                continue

            # Share handlers for same host (avoid duplicate SDK connections)
            if host in created_hosts:
                # Find existing handler for this host
                for dn, handler in self.domain_entity_handler_map.items():
                    if self.domain_name_to_host.get(dn) == host:
                        self.domain_entity_handler_map[domain_name] = handler
                        break
            else:
                handler = DomainEntityHandler(
                    all_entity_keys,
                    global_config_data=deepcopy(api_config),
                    entity_metadata_map=deepcopy(entity_metadata_map),
                )
                self.domain_entity_handler_map[domain_name] = handler
                created_hosts.add(host)

            # Initialise output skeleton for this domain
            self.output_skeleton["domains"][domain_name] = {"host": host}

    # ------------------------------------------------------------------
    # Dependency graph and topological sort
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dependency_graph(
        domain_entities: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, list[str]], dict[str, int]]:
        """Build a resource-level dependency graph from interpolation tokens.

        Scans every resource ``body``, ``params``, ``operations`` (and
        ``depends_on`` lists) for ``{resource_name.field}`` references and
        produces per-resource edges.  This avoids false cycles when two
        resources of the same entity type depend on each other through a
        third entity type (e.g. ``subnet -> vpc -> subnet``).

        Scanning ``params`` and ``operations`` ensures resources whose only
        references live outside ``body`` (e.g. an operations-only resource
        that associates other resources by ``{name.extId}``) are still
        ordered after the resources they reference.

        Args:
            domain_entities: ``{entity_type: {resource_name: resource_cfg}}``.

        Returns:
            ``(graph, in_degree)`` keyed by resource name, suitable for
            ``_topological_sort``.
        """
        resource_to_entity: dict[str, str] = {}
        for entity_type, resources in domain_entities.items():
            for resource_name in resources:
                resource_to_entity[resource_name] = entity_type

        known_resources = set(resource_to_entity)

        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)

        for _entity_type, resources in domain_entities.items():
            for resource_name, resource_cfg in resources.items():
                refs = extract_resource_refs(
                    [
                        resource_cfg.get("body", {}),
                        resource_cfg.get("params", {}),
                        resource_cfg.get("operations", []),
                    ],
                    known_resources,
                )

                for dep_name in resource_cfg.get("depends_on", []):
                    if dep_name in known_resources:
                        refs.add(dep_name)
                    else:
                        logger.warning(
                            f"depends_on entry '{dep_name}' in resource "
                            f"'{resource_name}' does not match any known "
                            f"resource in this domain."
                        )

                for ref in refs:
                    if ref != resource_name:
                        graph[ref].append(resource_name)
                        in_degree[resource_name] += 1

        for rname in known_resources:
            in_degree.setdefault(rname, 0)

        return graph, in_degree

    @staticmethod
    def _topological_sort(
        graph: dict[str, list[str]],
        in_degree: dict[str, int],
        entity_config_data: dict[str, Any],
    ) -> list[str]:
        """Kahn's algorithm for topological ordering.

        Works at the resource level.  ``entity_config_data`` may be keyed
        by entity type (legacy callers) or by resource name; the method
        only checks length for cycle detection.

        Raises:
            ValueError: On circular dependency.
        """
        queue: deque[str] = deque(node for node in in_degree if in_degree[node] == 0)
        sorted_nodes: list[str] = []

        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        total_nodes = sum(
            len(v) if isinstance(v, dict) else 1 for v in entity_config_data.values()
        )
        if len(sorted_nodes) != total_nodes:
            raise ValueError("Circular dependency detected in resource configuration")

        return sorted_nodes

    @staticmethod
    def _build_cross_domain_waves(
        domain_entity_map: dict[str, dict[str, dict[str, dict[str, Any]]]],
    ) -> list[list[str]]:
        """Toposort *domain_entity_map* into parallel waves by cross-domain refs.

        Edges go ``producer -> consumer`` (the consumer references the
        producer's state via ``{producer.<resource>.<field>}`` tokens),
        so wave 0 contains domains with no producers, wave 1 those that
        depend only on wave 0, and so on.  Domains within a wave have
        no inter-domain dependencies and can run in parallel.

        Args:
            domain_entity_map: ``{domain: {entity: {resource: cfg}}}``;
                pass ``self.domain_entity_resource_map`` for apply or
                ``self.previous_domain_entity_resource_map`` for destroy.

        Returns:
            List of waves; each wave is a list of domain names.

        Raises:
            ValueError: On circular cross-domain dependency.
        """
        all_domains = set(domain_entity_map)

        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = dict.fromkeys(all_domains, 0)

        for domain_name, entities in domain_entity_map.items():
            other_domains = all_domains - {domain_name}
            if not other_domains:
                continue
            for _entity, resources in entities.items():
                for _rname, rcfg in resources.items():
                    deps = extract_cross_domain_refs(
                        [
                            rcfg.get("body", {}),
                            rcfg.get("params", {}),
                            rcfg.get("operations", []),
                        ],
                        other_domains,
                    )
                    for dep in deps:
                        graph[dep].append(domain_name)
                        in_degree[domain_name] += 1

        waves: list[list[str]] = []
        remaining = dict(in_degree)

        while remaining:
            wave = [d for d, deg in remaining.items() if deg == 0]
            if not wave:
                raise ValueError(
                    "Circular cross-domain dependency detected among: "
                    + ", ".join(remaining)
                )
            waves.append(wave)
            for d in wave:
                for neighbor in graph[d]:
                    if neighbor in remaining:
                        remaining[neighbor] -= 1
            for d in wave:
                del remaining[d]

        return waves

    def _build_domain_dependency_order(self) -> list[list[str]]:
        """Build a wave-ordered list of domain groups for apply.

        Domains that reference other domains via cross-domain tokens
        (``{domain.resource.field}``) must wait for those domains to
        finish first.  Independent domains are grouped into the same
        wave so they can run in parallel.

        Returns:
            List of waves where each wave is a list of domain names
            that can be processed in parallel.

        Raises:
            ValueError: On circular cross-domain dependency.
        """
        return self._build_cross_domain_waves(self.domain_entity_resource_map)

    def _build_destroy_domain_waves(self) -> list[list[str]]:
        """Build wave-ordered destroy groups (apply order reversed).

        Destroy must tear down consumers before producers.  Cross-domain
        relationships are inferred from the **current** input config
        because state stores already-resolved bodies (the apply-time
        ``{domain.resource.field}`` tokens only survive in
        ``domain_entity_resource_map``).  Domains present in the
        previous state but no longer in config -- e.g. a config-deleted
        producer that still owns live resources -- are added as
        isolated nodes so they get a wave slot and aren't dropped from
        the destroy plan.  The apply-order waves are then reversed
        wave-by-wave; within each wave domains delete in parallel.

        Returns:
            List of waves; wave 0 is the consumer-most layer.

        Raises:
            ValueError: On circular cross-domain dependency in the
                current config.
        """
        merged: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
            d: dict(entities) for d, entities in self.domain_entity_resource_map.items()
        }
        for d in self.previous_domain_entity_resource_map:
            merged.setdefault(d, {})
        return list(reversed(self._build_cross_domain_waves(merged)))

    # ------------------------------------------------------------------
    # Interpolation helpers
    # ------------------------------------------------------------------

    def _build_interpolation_context(
        self,
        domain_name: str,
        resource_state: dict[str, dict[str, Any]],
        data_cache: dict[str, dict[str, dict[str, Any]]],
    ) -> InterpolationContext:
        """Create an interpolation context for the current domain."""
        # Cross-domain states (exclude current domain)
        other_domain_states = {
            dn: rs for dn, rs in self.domain_resource_state.items() if dn != domain_name
        }
        return InterpolationContext(
            variables=self.variables,
            resource_state=resource_state,
            data_cache=data_cache,
            domain_states=other_domain_states,
            current_domain=domain_name,
            functions=self.functions,
        )

    # ------------------------------------------------------------------
    # Data source fetching
    # ------------------------------------------------------------------

    def _fetch_single_data_source(
        self,
        entity_handler: DomainEntityHandler,
        entity_type: str,
        source_name: str,
        list_kwargs: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any], str | None]:
        """Fetch one data source entry (thread-safe).

        Returns:
            ``(entity_type, source_name, result_dict, error_key)`` where
            *error_key* is ``"entity_type/source_name"`` on failure or
            ``None`` on success.
        """
        try:
            results = entity_handler.list_entities(entity_type, **list_kwargs)
            sanitized_items: list[dict[str, Any]] = []
            for item in results:
                sanitized = entity_handler.sanitize_entity_data(entity_type, item)
                sanitized = strip_internal_attributes(sanitized)
                if isinstance(sanitized, dict):
                    sanitized_items.append(sanitized)
            if not sanitized_items and "_filter" in list_kwargs:
                logger.warning(
                    f"Data source {entity_type}/{source_name} returned no "
                    f"results for filter: {list_kwargs['_filter']!r}"
                )
            return (
                entity_type,
                source_name,
                {
                    "data": sanitized_items,
                    "metadata": {"totalAvailableResults": len(sanitized_items)},
                },
                None,
            )
        except Exception as exc:
            logger.error(
                f"Error fetching data source {entity_type}/{source_name}: {exc}"
            )
            return entity_type, source_name, {}, f"{entity_type}/{source_name}"

    def _fetch_data_sources(
        self,
        domain_name: str,
        entity_handler: DomainEntityHandler,
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
        """Fetch all data sources for a domain in parallel.

        Returns:
            A tuple of ``(cache, failures)`` where *cache* maps
            ``{entity_type: {source_name: {"data": [...], "metadata": {...}}}}``
            and *failures* is a list of ``"entity_type/source_name"``
            identifiers for sources that could not be fetched.
        """
        data_config = self.domain_data_config.get(domain_name, {})
        cache: dict[str, dict[str, dict[str, Any]]] = {}
        failures: list[str] = []
        alias_map = {
            "filter": "_filter",
            "select": "_select",
            "orderby": "_orderby",
            "limit": "_limit",
            "page": "_page",
        }

        tasks: list[tuple[str, str, dict[str, Any]]] = []
        for entity_type, sources in data_config.items():
            cache[entity_type] = {}
            for source_name, source_cfg in sources.items():
                list_kwargs: dict[str, Any] = {
                    key: value
                    for key, value in source_cfg.items()
                    if isinstance(key, str) and key.startswith("_")
                }
                for alias, target in alias_map.items():
                    if alias in source_cfg and target not in list_kwargs:
                        list_kwargs[target] = source_cfg[alias]
                if "_filter" not in list_kwargs:
                    logger.warning(
                        f"Data source {entity_type}/{source_name} has no filter."
                    )
                tasks.append((entity_type, source_name, list_kwargs))

        if not tasks:
            return cache, failures

        max_w = self.max_workers or len(tasks)
        worker_count = min(len(tasks), max_w)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self._fetch_single_data_source,
                    entity_handler,
                    et,
                    sn,
                    kw,
                ): (et, sn)
                for et, sn, kw in tasks
            }
            for future in as_completed(futures):
                et, sn, result, error_key = future.result()
                cache.setdefault(et, {})[sn] = result
                if error_key:
                    failures.append(error_key)

        return cache, failures

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    def _resolve_and_compare(
        self,
        resource_cfg: dict[str, Any],
        prev_item: dict[str, Any] | None,
        ctx: InterpolationContext,
        plan: bool = False,
    ) -> tuple[dict[str, Any], dict | None, dict, str | None, bool, str | None]:
        """Resolve interpolation and compare previous/current body.

        Returns:
            (resolved_resource, prev_body, curr_body, ext_id, update_needed, error_msg)
        """
        error_msg = None
        resource = deepcopy(resource_cfg)

        try:
            resource = resolve(resource, ctx, strict=not plan)
        except ValueError as exc:
            error_msg = str(exc)

        prev_body = prev_item.get("body", {}) if prev_item else None
        curr_body = resource.get("body", {})
        ext_id = None
        if prev_item:
            ext_id = prev_item.get("extId") or prev_item.get("ext_id")
        if not ext_id:
            ext_id = resource.get("extId") or resource.get("ext_id")

        # Apply ignore_changes before comparison
        rules = resource.get("rules", {})
        ignore_changes = rules.get("ignore_changes", [])

        try:
            cmp_prev, cmp_curr = _apply_ignore_changes(
                prev_body or {}, curr_body, ignore_changes
            )
            cmp_prev = _prune_prev_to_curr(cmp_prev, cmp_curr)
            is_equal = deep_equal(
                cmp_prev,
                cmp_curr,
                ignore_keys={"$objectType", "$dataItemDiscriminator"},
            )
        except Exception as exc:
            is_equal = False
            error_msg = error_msg or str(exc)

        update_needed = bool(ext_id and prev_body is not None and not is_equal)
        return resource, prev_body, curr_body, ext_id, update_needed, error_msg

    def _prepare_entity_upsert_results(
        self,
        entity: str,
        domain_name: str,
        entity_handler: DomainEntityHandler,
        input_resource_map: dict[str, Any],
        prev_resource_map: dict[str, Any],
        ctx: InterpolationContext,
        resource_state: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Create/update resources for a single entity type.

        Returns:
            Dict mapping resource_name → result dict (with ext_id, body, params).
        """
        entity_results: dict[str, dict[str, Any]] = {}
        run_results: dict[str, list] = {}
        replace_resources: list[tuple[str, dict, str, dict]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: dict[Any, tuple[str, dict[str, Any]]] = {}

            for resource_name, resource_cfg in input_resource_map.items():
                if _is_operations_only(resource_cfg):
                    continue

                prev_item = prev_resource_map.get(resource_name)
                resource, prev_body, curr_body, ext_id, update_needed, exc_msg = (
                    self._resolve_and_compare(resource_cfg, prev_item, ctx)
                )

                if exc_msg:
                    logger.error(
                        f"Error resolving interpolation for {entity}/{resource_name}: "
                        f"{exc_msg}"
                    )
                    if prev_item:
                        entity_results[resource_name] = prev_item
                        run_results.setdefault(domain_name, []).append(
                            {
                                "entity": entity,
                                "resource_name": resource_name,
                                "error": exc_msg,
                                "operation": "update",
                            }
                        )
                    else:
                        run_results.setdefault(domain_name, []).append(
                            {
                                "entity": entity,
                                "resource_name": resource_name,
                                "error": exc_msg,
                                "operation": "create",
                            }
                        )
                    continue

                handler_data = self._build_handler_data(resource, resource_name)

                rules = resource_cfg.get("rules", {})
                create_before_destroy = rules.get("create_before_destroy", False)
                entity_meta = entity_handler.entity_metadata_map.get(entity, {})
                update_supported = entity_meta.get("update_supported", True)
                if isinstance(update_supported, str):
                    update_supported = update_supported.lower() != "false"

                if (
                    ext_id
                    and update_needed
                    and not update_supported
                    and create_before_destroy
                ):
                    replace_resources.append(
                        (resource_name, resource, ext_id, handler_data)
                    )
                elif ext_id and update_needed:
                    ignore_changes = rules.get("ignore_changes", [])
                    if ignore_changes and prev_body:
                        handler_data["body"] = _merge_ignored_fields(
                            prev_body, handler_data["body"], ignore_changes
                        )
                    handler_data["ext_id"] = ext_id
                    thread_name = f"{domain_name}-{entity}-update"
                    futures[
                        executor.submit(
                            set_entity_thread_name(thread_name, entity_handler.update),
                            entity=entity,
                            data=handler_data,
                        )
                    ] = (resource_name, resource)
                elif ext_id and not update_needed:
                    # No change -- carry forward previous state (keep full body)
                    if prev_item:
                        # Refresh ``params``/``rules`` from the current
                        # config so that downstream interpolation of
                        # ``{resource.params.*}`` and lifecycle rule
                        # enforcement see the declared values rather
                        # than a stale copy from the previous state.
                        carried = dict(prev_item)
                        if "params" in resource:
                            carried["params"] = resource["params"]
                        if "rules" in resource:
                            carried["rules"] = resource["rules"]
                        entity_results[resource_name] = carried
                        resource_state[resource_name] = carried
                    else:
                        result_entry = self._build_state_entry(
                            resource, ext_id, body_override=prev_body or curr_body
                        )
                        entity_results[resource_name] = result_entry
                        resource_state[resource_name] = result_entry
                else:
                    thread_name = f"{domain_name}-{entity}-create"
                    futures[
                        executor.submit(
                            set_entity_thread_name(thread_name, entity_handler.create),
                            entity=entity,
                            data=handler_data,
                        )
                    ] = (resource_name, resource)

            for future in as_completed(futures):
                resource_name, resource = futures[future]
                result_ext_id = None
                try:
                    result_ext_id = future.result()
                except Exception as exc:
                    logger.error(f"Error processing {entity}/{resource_name}: {exc}")
                    logger.debug("Traceback:", exc_info=True)
                    # On failure: keep previous state if exists
                    if resource_name in prev_resource_map:
                        entity_results[resource_name] = prev_resource_map[resource_name]
                    run_results.setdefault(domain_name, []).append(
                        {
                            "entity": entity,
                            "resource_name": resource_name,
                            "error": str(exc),
                            "operation": (
                                "update"
                                if prev_resource_map.get(resource_name)
                                else "create"
                            ),
                        }
                    )
                    continue

                # Success
                ext_id = (
                    result_ext_id or resource.get("extId") or resource.get("ext_id")
                )
                latest_body = (
                    self._fetch_latest_body(entity, entity_handler, resource, ext_id)
                    if ext_id
                    else resource.get("body", {})
                )
                result_entry = self._build_state_entry(
                    resource, ext_id, body_override=latest_body
                )
                entity_results[resource_name] = result_entry
                resource_state[resource_name] = result_entry

                op_type = "update" if prev_resource_map.get(resource_name) else "create"
                run_results.setdefault(domain_name, []).append(
                    {
                        "entity": entity,
                        "resource_name": resource_name,
                        "extId": ext_id,
                        "error": None,
                        "operation": op_type,
                    }
                )

        # --- Handle create_before_destroy replacements ---
        for rname, resource, old_ext_id, handler_data in replace_resources:
            try:
                new_ext_id = entity_handler.create(
                    entity=entity, data=handler_data, resource_name=rname
                )
                if new_ext_id:
                    parent_kwargs = _extract_parent_kwargs(
                        entity, prev_resource_map.get(rname, {})
                    )
                    try:
                        entity_handler.delete(
                            entity=entity,
                            ext_id=old_ext_id,
                            resource_name=rname,
                            **parent_kwargs,
                        )
                    except Exception as del_exc:
                        logger.error(
                            f"create_before_destroy: created new "
                            f"{entity}/{rname} but failed to delete old "
                            f"(ext_id={old_ext_id}): {del_exc}"
                        )
                    latest_body = self._fetch_latest_body(
                        entity, entity_handler, resource, new_ext_id
                    )
                    result_entry = self._build_state_entry(
                        resource, new_ext_id, body_override=latest_body
                    )
                    entity_results[rname] = result_entry
                    resource_state[rname] = result_entry
                    run_results.setdefault(domain_name, []).append(
                        {
                            "entity": entity,
                            "resource_name": rname,
                            "extId": new_ext_id,
                            "error": None,
                            "operation": "replace",
                        }
                    )
                else:
                    raise RuntimeError(
                        f"create_before_destroy: create returned no ext_id "
                        f"for {entity}/{rname}"
                    )
            except Exception as exc:
                logger.error(
                    f"Error in create_before_destroy for {entity}/{rname}: {exc}"
                )
                if rname in prev_resource_map:
                    entity_results[rname] = prev_resource_map[rname]
                run_results.setdefault(domain_name, []).append(
                    {
                        "entity": entity,
                        "resource_name": rname,
                        "error": str(exc),
                        "operation": "replace",
                    }
                )

        self._accumulate_run_results(run_results)

        # --- Run per-resource operations ---
        for res_name, resource_cfg in input_resource_map.items():
            operations = resource_cfg.get("operations", [])
            for op in operations:
                self._run_operation(
                    entity, entity_handler, op, domain_name, ctx, res_name
                )

        return entity_results

    def _run_operation(
        self,
        entity: str,
        entity_handler: DomainEntityHandler,
        op: dict[str, Any],
        domain_name: str,
        ctx: InterpolationContext,
        resource_name: str | None = None,
    ) -> None:
        """Execute a single operation on a resource."""
        label = f"{entity}/{resource_name}" if resource_name else entity
        try:
            resolved_op = resolve(deepcopy(op), ctx)
            entity_handler.run_operation(
                entity=entity,
                operation_data=resolved_op,
                resource_name=resource_name,
            )
        except Exception as exc:
            logger.error(
                f"Error running operation {op.get('type')!r} on "
                f"'{label}' in domain {domain_name}: {exc}"
            )
            logger.debug("Traceback:", exc_info=True)

    @staticmethod
    def _build_handler_data(
        resource: dict[str, Any], resource_name: str
    ) -> dict[str, Any]:
        """Build the data dict passed to ``entity_handler.create/update``.

        Merges ``params`` into the top-level dict (for SDK method kwargs).
        """
        data: dict[str, Any] = {"body": resource.get("body", {})}
        params = resource.get("params", {})
        data.update(params)
        data["resource_name"] = resource_name
        return data

    @staticmethod
    def _build_state_entry(
        resource: dict[str, Any],
        ext_id: str | None,
        body_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a state entry for a resource.

        Lifecycle ``rules`` (e.g. ``prevent_destroy``) are persisted so
        they survive the resource being removed from config.
        """
        body = body_override if body_override is not None else resource.get("body", {})
        entry: dict[str, Any] = {"extId": ext_id, "body": body}
        if resource.get("params"):
            entry["params"] = resource["params"]
        rules = resource.get("rules")
        if rules:
            entry["rules"] = rules
        return entry

    def _fetch_latest_body(
        self,
        entity: str,
        entity_handler: DomainEntityHandler,
        resource: dict[str, Any],
        ext_id: str,
    ) -> dict[str, Any]:
        """Fetch and sanitize the latest entity body for state."""
        try:
            parent_kwargs = _extract_parent_kwargs(entity, resource)
            latest = entity_handler.get_entity_by_ext_id(
                entity, ext_id, **parent_kwargs
            )
            latest = entity_handler.sanitize_entity_data(entity, latest)
            latest = strip_internal_attributes(latest)
            if isinstance(latest, dict) and latest:
                return latest
        except Exception as exc:
            logger.warning(
                "Failed to fetch latest state for %s (ext_id=%s): %s",
                entity,
                ext_id,
                exc,
            )
        return resource.get("body", {})

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _prepare_delete_entity_results(
        self,
        entity: str,
        domain_name: str,
        entity_handler: DomainEntityHandler,
        resources_to_delete: dict[str, dict[str, Any]],
        rules_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Delete resources and return any that failed (to keep in state).

        Args:
            rules_map: Per-resource rules (from config or state).  Used to
                enforce ``prevent_destroy``.
        """
        surviving: dict[str, dict[str, Any]] = {}
        run_results: dict[str, list] = {}
        rules_map = rules_map or {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Store (resource_name, resource, ext_id) per future so the
            # as_completed loop records the ext_id of *this* future
            # rather than leaking the last-submitted value from the loop
            # variable (previous behaviour stamped every run_results row
            # with the same ext_id).
            futures: dict[Any, tuple[str, dict[str, Any], str]] = {}

            for resource_name, resource in resources_to_delete.items():
                # Check prevent_destroy rule
                resource_rules = rules_map.get(resource_name, {})
                if resource_rules.get("prevent_destroy", False):
                    logger.warning(
                        f"Skipping delete of {entity}/{resource_name}: "
                        f"prevent_destroy is enabled."
                    )
                    surviving[resource_name] = resource
                    continue

                ext_id = resource.get("extId") or resource.get("ext_id")
                if not ext_id:
                    continue

                parent_kwargs = _extract_parent_kwargs(entity, resource)
                thread_name = f"{domain_name}-{entity}-delete"
                futures[
                    executor.submit(
                        set_entity_thread_name(thread_name, entity_handler.delete),
                        entity=entity,
                        ext_id=ext_id,
                        resource_name=resource_name,
                        **parent_kwargs,
                    )
                ] = (resource_name, resource, ext_id)

            for future in as_completed(futures):
                resource_name, resource, fut_ext_id = futures[future]
                try:
                    future.result()
                    run_results.setdefault(domain_name, []).append(
                        {
                            "entity": entity,
                            "resource_name": resource_name,
                            "extId": fut_ext_id,
                            "error": None,
                            "operation": "delete",
                        }
                    )
                except Exception as exc:
                    logger.error(f"Error deleting {entity}/{resource_name}: {exc}")
                    logger.debug("Traceback:", exc_info=True)
                    surviving[resource_name] = resource
                    run_results.setdefault(domain_name, []).append(
                        {
                            "entity": entity,
                            "resource_name": resource_name,
                            "extId": fut_ext_id,
                            "error": str(exc),
                            "operation": "delete",
                        }
                    )

        self._accumulate_run_results(run_results)
        return surviving

    # ------------------------------------------------------------------
    # Domain-level orchestration
    # ------------------------------------------------------------------

    def _run_domain_for_upsert(
        self,
        domain_name: str,
        on_state_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], str]:
        """Create/update all resources in a domain (topological order)."""
        try:
            entity_handler = self.domain_entity_handler_map[domain_name]
            domain_entities = self.domain_entity_resource_map[domain_name]

            # Fetch data sources
            data_cache, ds_failures = self._fetch_data_sources(
                domain_name, entity_handler
            )
            self.domain_data_cache[domain_name] = data_cache
            if ds_failures:
                logger.warning(
                    "Domain '%s': %d data source(s) failed to fetch: %s. "
                    "Resources depending on these will fail.",
                    domain_name,
                    len(ds_failures),
                    ", ".join(ds_failures),
                )

            # Resource state for interpolation (grows as resources are created)
            resource_state: dict[str, dict[str, Any]] = {}

            # Pre-populate resource_state from previous state
            for _, eresources in self.previous_domain_entity_resource_map.get(
                domain_name, {}
            ).items():
                for rname, rdata in eresources.items():
                    resource_state[rname] = rdata

            # Resource-level topological sort
            graph, in_degree = self._build_dependency_graph(domain_entities)
            sorted_resources = self._topological_sort(graph, in_degree, domain_entities)

            resource_to_entity: dict[str, str] = {}
            for etype, resources in domain_entities.items():
                for rname in resources:
                    resource_to_entity[rname] = etype

            # Derive entity-type order (first appearance) for delete
            seen_entity_types: set[str] = set()
            entity_order: list[str] = []
            resource_order: list[tuple[str, str]] = []
            for rname in sorted_resources:
                etype = resource_to_entity[rname]
                resource_order.append((etype, rname))
                if etype not in seen_entity_types:
                    seen_entity_types.add(etype)
                    entity_order.append(etype)
            self.domain_entity_order[domain_name] = entity_order
            self.domain_resource_order[domain_name] = resource_order

            domain_results: dict[str, dict[str, dict[str, Any]]] = {}

            for entity, rname in resource_order:
                if self._shutdown_requested.is_set():
                    logger.warning(
                        "Shutdown requested -- stopping domain '%s' "
                        "after %d resource(s).",
                        domain_name,
                        sum(len(v) for v in domain_results.values()),
                    )
                    break

                resource_cfg = domain_entities[entity][rname]
                prev_resource_map = self.previous_domain_entity_resource_map.get(
                    domain_name, {}
                ).get(entity, {})

                ctx = self._build_interpolation_context(
                    domain_name, resource_state, data_cache
                )

                entity_results = self._prepare_entity_upsert_results(
                    entity,
                    domain_name,
                    entity_handler,
                    {rname: resource_cfg},
                    prev_resource_map,
                    ctx,
                    resource_state,
                )

                if entity_results:
                    domain_results.setdefault(entity, {}).update(entity_results)

                self._update_partial_results(
                    domain_name, domain_results, on_state_change
                )

            # Update cross-domain state for other domains to reference
            self.domain_resource_state[domain_name] = resource_state

            return domain_results, domain_name

        except Exception as exc:
            logger.error(
                f"Exception in _run_domain_for_upsert for domain '{domain_name}': {exc}"
            )
            logger.debug("Traceback:", exc_info=True)
            prev = dict(self.previous_domain_entity_resource_map.get(domain_name, {}))
            return prev, domain_name

    def _run_domain_for_delete(
        self,
        domain_name: str,
        entities_to_delete: dict[str, dict[str, dict[str, Any]]],
        entity_rules_map: dict[str, dict[str, dict[str, Any]]] | None = None,
        on_state_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], str]:
        """Delete resources in reverse topological order.

        Args:
            domain_name: The domain whose resources to delete.
            entities_to_delete: ``{entity: {resource_name: resource_data}}``.
            entity_rules_map: ``{entity: {resource_name: rules_dict}}``.
                Used to enforce ``prevent_destroy``.
        """
        try:
            entity_handler = self.domain_entity_handler_map[domain_name]
            entity_rules_map = entity_rules_map or {}

            delete_names: set[str] = set()
            for entity_resources in entities_to_delete.values():
                delete_names.update(entity_resources)

            # Build dependency order from input config (has tokens) or
            # stored order from a prior apply in this session
            stored_resource_order = self.domain_resource_order.get(domain_name, [])
            if stored_resource_order:
                ordered_pairs: list[tuple[str, str]] = [
                    (etype, rname)
                    for etype, rname in stored_resource_order
                    if rname in delete_names
                ]
            else:
                # Rebuild graph from input config which has interpolation tokens
                input_entities = self.domain_entity_resource_map.get(domain_name, {})
                graph_source = input_entities if input_entities else entities_to_delete
                graph, in_degree = self._build_dependency_graph(graph_source)
                sorted_resources = self._topological_sort(
                    graph, in_degree, graph_source
                )
                resource_to_entity: dict[str, str] = {}
                for etype, resources in graph_source.items():
                    for rname in resources:
                        resource_to_entity[rname] = etype
                ordered_pairs = [
                    (resource_to_entity[rname], rname)
                    for rname in sorted_resources
                    if rname in delete_names
                ]

            # Add any remaining resources not covered by the ordering
            covered = {rname for _, rname in ordered_pairs}
            for entity, entity_resources in entities_to_delete.items():
                for rname in entity_resources:
                    if rname not in covered:
                        ordered_pairs.append((entity, rname))

            deleted_names: set[str] = set()
            surviving: dict[str, dict[str, dict[str, Any]]] = {}

            for entity, rname in reversed(ordered_pairs):
                if self._shutdown_requested.is_set():
                    logger.warning(
                        "Shutdown requested -- stopping delete in domain "
                        "'%s'. Remaining resources kept in state.",
                        domain_name,
                    )
                    break

                rdata = entities_to_delete.get(entity, {}).get(rname)
                if rdata is None:
                    continue
                rules_map = entity_rules_map.get(entity, {})
                surviving_resources = self._prepare_delete_entity_results(
                    entity,
                    domain_name,
                    entity_handler,
                    {rname: rdata},
                    rules_map=rules_map,
                )
                if surviving_resources:
                    surviving.setdefault(entity, {}).update(surviving_resources)
                else:
                    deleted_names.add(rname)

                self._remove_deleted_from_partial_results(
                    domain_name, deleted_names, on_state_change
                )

            for entity, entity_resources in entities_to_delete.items():
                for rn, rd in entity_resources.items():
                    if rn not in deleted_names and rn not in surviving.get(entity, {}):
                        surviving.setdefault(entity, {}).update({rn: rd})

            return surviving, domain_name

        except Exception as exc:
            logger.error(
                f"Exception in _run_domain_for_delete for domain '{domain_name}': {exc}"
            )
            logger.debug("Traceback:", exc_info=True)
            return entities_to_delete, domain_name

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    def run(
        self,
        on_state_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Apply config: create/update/delete resources.

        State is persisted incrementally after every resource operation
        via ``on_state_change``.  If the process is interrupted, call
        ``get_partial_state()`` to retrieve the last known good state.

        Args:
            on_state_change: Optional callback invoked with intermediate state
                after each resource completes.  Used for incremental persistence.

        Returns:
            New state dict (``{"domains": {...}}``).
        """
        with self._partial_results_lock:
            self._partial_results.clear()

        resources_to_delete: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

        # Determine what to delete
        for domain_name, resource_names in self.domain_resource_name_map.items():
            prev_names = self.previous_domain_resource_name_map.get(domain_name, set())
            names_to_delete = prev_names - resource_names
            if names_to_delete:
                prev_entities = self.previous_domain_entity_resource_map.get(
                    domain_name, {}
                )
                domain_deletes: dict[str, dict[str, dict[str, Any]]] = {}
                for entity, entity_resources in prev_entities.items():
                    to_del = {
                        rn: rd
                        for rn, rd in entity_resources.items()
                        if rn in names_to_delete
                    }
                    if to_del:
                        domain_deletes[entity] = to_del
                if domain_deletes:
                    resources_to_delete[domain_name] = domain_deletes

        # Domains in state but not in config → delete all
        for domain_name in self.previous_domain_resource_name_map:
            if domain_name not in self.domain_resource_name_map:
                prev_entities = self.previous_domain_entity_resource_map.get(
                    domain_name, {}
                )
                if prev_entities:
                    resources_to_delete[domain_name] = prev_entities

        # --- Create/Update (wave-ordered for cross-domain deps) ---
        domain_waves = self._build_domain_dependency_order()
        for wave in domain_waves:
            with ThreadPoolExecutor(max_workers=max(len(wave), 1)) as executor:
                upsert_futures = []
                for domain_name in wave:
                    upsert_futures.append(
                        executor.submit(
                            set_entity_thread_name(
                                domain_name, self._run_domain_for_upsert
                            ),
                            domain_name=domain_name,
                            on_state_change=on_state_change,
                        )
                    )
                for future in as_completed(upsert_futures):
                    try:
                        future.result()
                    except Exception as exc:
                        logger.error(f"Error in upsert for a domain: {exc}")
                        logger.debug("Traceback:", exc_info=True)

        # --- Delete ---
        if not self._shutdown_requested.is_set():
            with ThreadPoolExecutor(
                max_workers=max(len(resources_to_delete), 1)
            ) as executor:
                delete_futures = []
                for domain_name, to_delete in resources_to_delete.items():
                    if domain_name not in self.domain_entity_handler_map:
                        continue
                    entity_rules: dict[str, dict[str, dict[str, Any]]] = {}
                    for entity, entity_resources in to_delete.items():
                        entity_rules[entity] = {}
                        for rn in entity_resources:
                            cfg = (
                                self.domain_entity_resource_map.get(domain_name, {})
                                .get(entity, {})
                                .get(rn, {})
                            )
                            rules = cfg.get("rules", {})
                            if not rules:
                                rules = entity_resources[rn].get("rules", {})
                            entity_rules[entity][rn] = rules
                    delete_futures.append(
                        executor.submit(
                            set_entity_thread_name(
                                f"{domain_name}-delete",
                                self._run_domain_for_delete,
                            ),
                            domain_name=domain_name,
                            entities_to_delete=to_delete,
                            entity_rules_map=entity_rules,
                            on_state_change=on_state_change,
                        )
                    )
                for future in as_completed(delete_futures):
                    try:
                        surviving, domain_name = future.result()
                        if surviving:
                            with self._partial_results_lock:
                                self._partial_results.setdefault(domain_name, {})
                                for entity, resources in surviving.items():
                                    self._partial_results[domain_name].setdefault(
                                        entity, {}
                                    ).update(resources)
                    except Exception as exc:
                        logger.error(f"Error in delete for a domain: {exc}")
                        logger.debug("Traceback:", exc_info=True)

        # --- Write audit file and build output state ---
        self._write_run_results(self._run_results)
        return self.get_partial_state()

    def destroy(
        self,
        on_state_change: Callable[[dict[str, Any]], None] | None = None,
        entity_rules_map: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Destroy all resources in the previous state.

        State is persisted incrementally after every resource deletion.
        If the process is interrupted, call ``get_partial_state()`` to
        retrieve surviving resources.

        Args:
            on_state_change: Optional callback invoked with intermediate state
                after each resource deletion.
            entity_rules_map: Optional per-domain per-entity rules map
                ``{domain: {entity: {resource_name: rules_dict}}}``.
                When supplied, ``prevent_destroy`` rules are enforced.

        Returns:
            New state dict with any surviving (failed-to-delete) resources.
        """
        with self._partial_results_lock:
            self._partial_results.clear()

        all_to_delete: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

        for (
            domain_name,
            prev_entities,
        ) in self.previous_domain_entity_resource_map.items():
            if prev_entities:
                all_to_delete[domain_name] = dict(prev_entities)
                # Seed partial results so un-attempted resources survive
                with self._partial_results_lock:
                    self._partial_results[domain_name] = dict(prev_entities)

        # Reverse-toposort domains by cross-domain refs so that consumers
        # are torn down before their producers; each wave still runs in
        # parallel internally, preserving today's per-domain throughput
        # for graphs without inter-domain refs (single wave).
        destroy_waves = self._build_destroy_domain_waves()

        for wave in destroy_waves:
            wave_targets = {
                domain_name: all_to_delete[domain_name]
                for domain_name in wave
                if domain_name in all_to_delete
            }
            if not wave_targets:
                continue
            if self._shutdown_requested.is_set():
                break
            with ThreadPoolExecutor(max_workers=max(len(wave_targets), 1)) as executor:
                futures = []
                for domain_name, to_delete in wave_targets.items():
                    if domain_name not in self.domain_entity_handler_map:
                        logger.warning(
                            f"No handler for domain '{domain_name}'. "
                            f"Cannot destroy resources."
                        )
                        continue
                    domain_rules = (entity_rules_map or {}).get(domain_name, {})
                    futures.append(
                        executor.submit(
                            set_entity_thread_name(
                                f"{domain_name}-destroy",
                                self._run_domain_for_delete,
                            ),
                            domain_name=domain_name,
                            entities_to_delete=to_delete,
                            entity_rules_map=domain_rules,
                            on_state_change=on_state_change,
                        )
                    )
                for future in as_completed(futures):
                    try:
                        surviving, domain_name = future.result()
                        with self._partial_results_lock:
                            if surviving:
                                self._partial_results[domain_name] = surviving
                            else:
                                self._partial_results.pop(domain_name, None)
                    except Exception as exc:
                        logger.error(f"Error in destroy for a domain: {exc}")
                        logger.debug("Traceback:", exc_info=True)

        self._write_run_results(self._run_results)
        return self.get_partial_state()

    def plan(self) -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
        """Show what would change without applying.

        Returns:
            ``{"create": {...}, "update": {...}, "delete": {...}}``
        """
        plan_result: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {
            "create": defaultdict(lambda: defaultdict(list)),
            "update": defaultdict(lambda: defaultdict(list)),
            "delete": defaultdict(lambda: defaultdict(list)),
            "operations": defaultdict(lambda: defaultdict(list)),
        }

        # Determine deletes
        resources_to_delete_names: dict[str, set] = {}
        for domain_name, resource_names in self.domain_resource_name_map.items():
            prev_names = self.previous_domain_resource_name_map.get(domain_name, set())
            resources_to_delete_names[domain_name] = prev_names - resource_names

        for domain_name in self.previous_domain_resource_name_map:
            if domain_name not in self.domain_resource_name_map:
                resources_to_delete_names[domain_name] = (
                    self.previous_domain_resource_name_map[domain_name]
                )

        # Plan create/update
        for domain_name in self.domain_entity_resource_map:
            entity_handler = self.domain_entity_handler_map.get(domain_name)
            if not entity_handler:
                continue

            # Build a resource_state from previous state for interpolation
            resource_state: dict[str, dict[str, Any]] = {}
            for _, eres in self.previous_domain_entity_resource_map.get(
                domain_name, {}
            ).items():
                for rn, rd in eres.items():
                    resource_state[rn] = rd

            # Fetch data sources for accurate plan interpolation
            try:
                data_cache, ds_failures = self._fetch_data_sources(
                    domain_name, entity_handler
                )
            except Exception as ds_exc:
                logger.warning(
                    "Failed to fetch data sources for '%s' during plan: %s. "
                    "Data source interpolation may be inaccurate.",
                    domain_name,
                    ds_exc,
                )
                data_cache = {}
                ds_failures = []
            if ds_failures:
                logger.warning(
                    "Domain '%s': %d data source(s) failed to fetch: %s. "
                    "Plan output for this domain may be inaccurate.",
                    domain_name,
                    len(ds_failures),
                    ", ".join(ds_failures),
                )
            ctx = self._build_interpolation_context(
                domain_name, resource_state, data_cache
            )

            domain_entities = self.domain_entity_resource_map[domain_name]
            for entity, input_resource_map in domain_entities.items():
                prev_resource_map = self.previous_domain_entity_resource_map.get(
                    domain_name, {}
                ).get(entity, {})
                for resource_name, resource_cfg in input_resource_map.items():
                    prev_item = prev_resource_map.get(resource_name)
                    resource, prev_body, curr_body, ext_id, update_needed, exc_msg = (
                        self._resolve_and_compare(
                            resource_cfg, prev_item, ctx, plan=True
                        )
                    )
                    if exc_msg:
                        logger.error(
                            f"Plan error for {entity}/{resource_name}: {exc_msg}"
                        )
                        continue

                    operations = resource_cfg.get("operations", [])
                    is_ops_only = _is_operations_only(resource_cfg)

                    if not is_ops_only:
                        plan_entry: dict[str, Any] = {
                            "resource_name": resource_name,
                            **{
                                k: v
                                for k, v in resource.items()
                                if k not in _NON_CRUD_KEYS
                            },
                        }

                        if ext_id and update_needed:
                            rules = resource_cfg.get("rules", {})
                            ignore_changes = rules.get("ignore_changes", [])
                            filt_prev, filt_curr = _apply_ignore_changes(
                                prev_body or {}, curr_body, ignore_changes
                            )
                            pruned_prev = _prune_prev_to_curr(filt_prev, filt_curr)
                            diff_fields = _compute_field_diff(pruned_prev, filt_curr)
                            plan_entry["diff_fields"] = diff_fields
                            plan_result["update"][domain_name][entity].append(
                                plan_entry
                            )
                        elif ext_id and not update_needed:
                            pass
                        else:
                            plan_result["create"][domain_name][entity].append(
                                plan_entry
                            )

                    for op in operations:
                        plan_result["operations"][domain_name][entity].append(
                            {
                                "resource_name": resource_name,
                                "type": op.get("type"),
                            }
                        )

        # Plan delete
        for domain_name, names_to_delete in resources_to_delete_names.items():
            prev_entities = self.previous_domain_entity_resource_map.get(
                domain_name, {}
            )
            for entity, resources in prev_entities.items():
                for rn, rd in resources.items():
                    if rn in names_to_delete:
                        plan_result["delete"][domain_name][entity].append(
                            {
                                "resource_name": rn,
                                "body": rd.get("body"),
                            }
                        )

        # Convert defaultdicts → plain dicts
        return {
            action: {d: dict(ents) for d, ents in domains.items()}
            for action, domains in plan_result.items()
        }

    def _refresh_single_resource(
        self,
        entity_handler: DomainEntityHandler,
        entity: str,
        resource_name: str,
        resource_data: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Fetch the latest state for a single resource.

        Args:
            entity_handler: Handler for the domain.
            entity: Entity type name.
            resource_name: Logical resource name.
            resource_data: Previous state entry for this resource.

        Returns:
            ``(resource_name, entity, refreshed_entry)`` where
            *refreshed_entry* is ``None`` when the resource was removed
            (404).
        """
        ext_id = resource_data.get("extId") or resource_data.get("ext_id")
        if not ext_id:
            return resource_name, entity, resource_data

        try:
            parent_kwargs = _extract_parent_kwargs(entity, resource_data)
            latest = entity_handler.get_entity_by_ext_id(
                entity, ext_id, **parent_kwargs
            )
            latest = entity_handler.sanitize_entity_data(entity, latest)
            latest = strip_internal_attributes(latest)

            if not latest:
                return resource_name, entity, resource_data

            refreshed_body = latest if isinstance(latest, dict) else {}
            entry: dict[str, Any] = {"extId": ext_id, "body": refreshed_body}
            if resource_data.get("params"):
                entry["params"] = resource_data["params"]
            if resource_data.get("rules"):
                entry["rules"] = resource_data["rules"]
            return resource_name, entity, entry

        except Exception as exc:
            status = getattr(exc, "status", None)
            if status == 404:
                logger.info(
                    "Resource %s/%s (extId=%s) not found in "
                    "infrastructure (404). Removing from state.",
                    entity,
                    resource_name,
                    ext_id,
                )
                return resource_name, entity, None
            logger.warning(
                "Error refreshing %s/%s (status=%s): %s. Keeping previous state.",
                entity,
                resource_name,
                status,
                exc,
            )
            return resource_name, entity, resource_data

    def _refresh_domain(
        self,
        domain_name: str,
        prev_entities: dict[str, dict[str, dict[str, Any]]],
    ) -> tuple[str, dict[str, Any]]:
        """Refresh all resources for a single domain in parallel.

        Args:
            domain_name: Domain key.
            prev_entities: ``{entity: {resource_name: resource_data}}``
                from previous state.

        Returns:
            ``(domain_name, refreshed_domain_dict)``.
        """
        entity_handler = self.domain_entity_handler_map.get(domain_name)
        if not entity_handler:
            logger.warning(f"No handler for domain '{domain_name}'. Skipping refresh.")
            return domain_name, {}

        host = self.domain_name_to_host.get(domain_name, domain_name)
        refreshed_domain: dict[str, Any] = {"host": host, "resources": {}}

        resource_items = [
            (entity, rn, rd)
            for entity, entity_resources in prev_entities.items()
            for rn, rd in entity_resources.items()
        ]

        # ``min(len(resource_items), cap)`` can collapse to 0 when the
        # domain has nothing to refresh, which would raise
        # ``ValueError: max_workers must be greater than 0``.  Clamp to
        # at least 1 so the ``with`` block is always valid; when the
        # iterable is empty the executor simply has no work to do.
        with ThreadPoolExecutor(
            max_workers=max(1, min(len(resource_items), self.max_workers or 8))
        ) as executor:
            futures = {
                executor.submit(
                    self._refresh_single_resource,
                    entity_handler,
                    entity,
                    rn,
                    rd,
                ): (entity, rn)
                for entity, rn, rd in resource_items
            }
            for future in as_completed(futures):
                rn, entity, entry = future.result()
                if entry is not None:
                    refreshed_domain["resources"].setdefault(entity, {})[rn] = entry

        return domain_name, refreshed_domain

    def refresh_state(self) -> dict[str, Any]:
        """Fetch latest resource state from infrastructure.

        Domains are refreshed in parallel, and within each domain all
        resources are fetched concurrently.

        Returns:
            Updated state dict.
        """
        try:
            refreshed: dict[str, Any] = {"domains": {}}
            domains_to_refresh = dict(self.previous_domain_entity_resource_map.items())

            with ThreadPoolExecutor(
                max_workers=max(len(domains_to_refresh), 1)
            ) as executor:
                futures = [
                    executor.submit(
                        set_entity_thread_name(f"{dn}-refresh", self._refresh_domain),
                        domain_name=dn,
                        prev_entities=prev_entities,
                    )
                    for dn, prev_entities in domains_to_refresh.items()
                ]
                for future in as_completed(futures):
                    try:
                        dn, domain_result = future.result()
                        if domain_result:
                            refreshed["domains"][dn] = domain_result
                    except Exception as exc:
                        logger.error(f"Error refreshing domain: {exc}")
                        logger.debug("Traceback:", exc_info=True)

            return refreshed

        except Exception as exc:
            logger.error(f"Error during refresh_state: {exc}")
            logger.debug("Traceback:", exc_info=True)
            return deepcopy(self.previous_state)

    def import_resource_data(
        self, resource_name: str, domain_name: str
    ) -> dict[str, Any] | None:
        """Fetch a resource by extId/ext_id for import.

        If the ``extId`` contains interpolation tokens (e.g. data-source
        references like ``{data.category.foo.extId}`` or variable
        references like ``{var.x}``), they are resolved automatically
        before the API call.

        Args:
            resource_name: Name of the resource in the config.
            domain_name: Domain name (key in ``domains:``).

        Returns:
            Dict with entity_name, sanitized_data, extId, resource_entry,
            domain info.
        """
        domains = self.config.get("domains", {})
        domain_cfg = domains.get(domain_name)
        if not domain_cfg:
            raise ValueError(f"Domain '{domain_name}' not found in config.")

        # Find the entity and resource
        entity_name = None
        resource_entry = None
        for etype, eresources in domain_cfg.get("resources", {}).items():
            if resource_name in eresources:
                entity_name = etype
                resource_entry = eresources[resource_name]
                break

        if not entity_name or resource_entry is None:
            raise ValueError(
                f"Resource '{resource_name}' not found in config for "
                f"domain '{domain_name}'."
            )

        entity_handler = self.domain_entity_handler_map.get(domain_name)
        if not entity_handler:
            raise ValueError(f"No entity handler for domain '{domain_name}'.")

        ext_id = resource_entry.get("extId") or resource_entry.get("ext_id")
        if not ext_id:
            raise ValueError(f"No ext_id/extId found for resource '{resource_name}'.")

        # Resolve interpolation tokens in ext_id (data sources, variables, etc.)
        if isinstance(ext_id, str) and has_tokens(ext_id):
            data_cache = self.domain_data_cache.get(domain_name)
            if data_cache is None:
                data_cache, ds_failures = self._fetch_data_sources(
                    domain_name, entity_handler
                )
                self.domain_data_cache[domain_name] = data_cache
                if ds_failures:
                    logger.warning(
                        "Domain '%s': %d data source(s) failed during import: %s",
                        domain_name,
                        len(ds_failures),
                        ", ".join(ds_failures),
                    )

            resource_state: dict[str, dict[str, Any]] = {}
            ctx = self._build_interpolation_context(
                domain_name, resource_state, data_cache
            )
            ext_id = resolve(ext_id, ctx)

            if has_tokens(str(ext_id)):
                raise ValueError(
                    f"ext_id for '{resource_name}' still contains unresolved "
                    f"tokens after interpolation: {ext_id}"
                )

        parent_kwargs = _extract_parent_kwargs(entity_name, resource_entry)
        entity_data = entity_handler.get_entity_by_ext_id(
            entity_name, ext_id, **parent_kwargs
        )
        sanitized = entity_handler.sanitize_entity_data(entity_name, entity_data)
        stripped = strip_internal_attributes_for_an_entity(sanitized, entity_name)

        return {
            "entity_name": entity_name,
            "sanitized_data": stripped,
            "extId": ext_id,
            "resource_entry": resource_entry,
            "domain_name": domain_name,
        }

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def resolve_outputs(self) -> dict[str, Any]:
        """Resolve output expressions using the final resource state.

        Returns:
            ``{output_name: {"value": resolved, "description": ...}}``
        """
        if not self.outputs_config:
            return {}

        # Build a combined resource_state from all domains
        all_resource_state: dict[str, dict[str, Any]] = {}
        for _, rs in self.domain_resource_state.items():
            all_resource_state.update(rs)

        if len(self.domain_data_cache) == 1:
            data_cache = next(iter(self.domain_data_cache.values()))
        else:
            data_cache = dict(self.domain_data_cache)

        # Build domain states for cross-domain references
        ctx = InterpolationContext(
            variables=self.variables,
            resource_state=all_resource_state,
            data_cache=data_cache,
            domain_states=dict(self.domain_resource_state),
            functions=self.functions,
        )

        resolved_outputs: dict[str, Any] = {}
        for output_name, output_cfg in self.outputs_config.items():
            try:
                resolved_value = resolve(output_cfg.get("value", ""), ctx)
                resolved_outputs[output_name] = {
                    "value": resolved_value,
                    "description": output_cfg.get("description", ""),
                }
            except ValueError as exc:
                logger.error(f"Error resolving output '{output_name}': {exc}")
                resolved_outputs[output_name] = {
                    "value": None,
                    "description": output_cfg.get("description", ""),
                    "error": str(exc),
                }

        return resolved_outputs

    def request_shutdown(self) -> None:
        """Signal domain runners to stop after the current resource."""
        self._shutdown_requested.set()

    def _update_partial_results(
        self,
        domain_name: str,
        domain_results: dict[str, dict[str, dict[str, Any]]],
        on_state_change: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        """Thread-safe update of partial results and optional state write."""
        with self._partial_results_lock:
            self._partial_results[domain_name] = domain_results
            if on_state_change:
                on_state_change(self._build_output_state(self._partial_results))

    def _remove_deleted_from_partial_results(
        self,
        domain_name: str,
        deleted_names: set[str],
        on_state_change: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        """Remove successfully deleted resources from partial results.

        Unlike ``_update_partial_results`` which replaces the entire
        domain entry, this method only removes the named resources,
        preserving any resources created/updated in the upsert phase.
        """
        with self._partial_results_lock:
            domain_results = self._partial_results.get(domain_name, {})
            for entity in list(domain_results):
                for rname in list(domain_results[entity]):
                    if rname in deleted_names:
                        del domain_results[entity][rname]
                if not domain_results[entity]:
                    del domain_results[entity]
            if on_state_change:
                on_state_change(self._build_output_state(self._partial_results))

    def get_partial_state(self) -> dict[str, Any]:
        """Return state built from whatever results have been accumulated.

        Safe to call from a signal or interrupt handler.
        """
        with self._partial_results_lock:
            return self._build_output_state(self._partial_results)

    def _build_output_state(
        self,
        results_per_domain: dict[str, dict[str, dict[str, dict[str, Any]]]],
    ) -> dict[str, Any]:
        """Build the final state dict from per-domain results."""
        state: dict[str, Any] = {"domains": {}}

        for domain_name in self.output_skeleton["domains"]:
            host = self.output_skeleton["domains"][domain_name].get("host", domain_name)
            domain_state: dict[str, Any] = {"host": host, "resources": {}}

            entity_order = self.domain_entity_order.get(domain_name)
            if entity_order:
                domain_state["_entity_order"] = entity_order

            domain_results = results_per_domain.get(domain_name, {})
            for entity, entity_resources in domain_results.items():
                if entity_resources:
                    domain_state["resources"][entity] = entity_resources

            if domain_state["resources"]:
                state["domains"][domain_name] = domain_state

        logger.info("State prepared.")
        logger.debug(json.dumps(state, indent=2))
        return state

    def _accumulate_run_results(self, run_results: dict[str, list]) -> None:
        """Thread-safely merge per-entity run results into the instance accumulator."""
        if not run_results:
            return
        with self._run_results_lock:
            for domain, results in run_results.items():
                if domain in self._run_results:
                    self._run_results[domain].extend(results)
                else:
                    self._run_results[domain] = list(results)

    @property
    def run_results(self) -> dict[str, list[dict[str, Any]]]:
        """Return accumulated run results from the last run/destroy call."""
        return dict(self._run_results)

    def _write_run_results(
        self,
        run_results: dict[str, list],
        *,
        interrupted: bool | None = None,
    ) -> None:
        """Persist the run audit JSON next to the state file.

        The output file is a wrapper object so future diagnostics (counts,
        durations, etc.) can be added without invalidating existing
        consumers again.  The wrapper shape is::

            {
                "metadata": {
                    "interrupted": bool,
                    "completed_at": "<UTC ISO-8601>"
                },
                "results": {"<domain>": [ ... ]}
            }

        Args:
            run_results: Accumulator mapping domain name to per-entity
                operation result rows.
            interrupted: When ``True``, records that the run was stopped
                early (e.g. Ctrl-C during apply/destroy).  When ``None``
                the flag is derived from ``self._shutdown_requested``.
        """
        if not run_results:
            return

        if interrupted is None:
            interrupted = self._shutdown_requested.is_set()

        payload: dict[str, Any] = {
            "metadata": {
                "interrupted": bool(interrupted),
                "completed_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
            },
            "results": run_results,
        }

        target = Path(self.run_results_path)
        # ``parent`` is empty for a bare filename; ``mkdir(parents=True,
        # exist_ok=True)`` is a no-op in that case.
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
