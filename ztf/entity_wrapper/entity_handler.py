import importlib
import inspect
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import inflect
import orjson
import urllib3
from ntnx_prism_py_client.models.prism.v4.config.TaskStatus import TaskStatus

from ztf.sdk_utils import call_api_with_body, deep_merge
from ztf.state_monitor.task_monitor import PcTaskMonitor
from ztf.utils.utils import (
    ColoredFormatter,
    get_logger,
    raise_api_exception,
    redact_secrets,
    snake_to_camel,
    strip_internal_attributes,
)

from .entity_map import entity_map  # Import the entity_map

p = inflect.engine()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class _RestLogFilter(logging.Filter):
    """Block SDK rest module messages from console stream handlers."""

    def __init__(self, rest_logger_name: str) -> None:
        super().__init__()
        self._prefix = rest_logger_name

    def filter(self, record: logging.LogRecord) -> bool:
        """Allow only records that do NOT originate from the rest logger."""
        return not record.name.startswith(self._prefix)


# Default path for the compatibility map (sibling file in entity_wrapper/)
_COMPAT_MAP_PATH = (
    Path(__file__).resolve().parent / "multi_namespace_compatibility_map.json"
)

# Module-level singleton: loaded once, shared across all DomainEntityHandler instances
_compat_map_cache: dict[str, Any] | None = None

# SDK ApiClient classes already patched with the negotiate_version override
_patched_api_clients: set = set()

_patch_logger = get_logger(__name__)


def _patched_negotiate_version(self, auth_settings: Any) -> None:
    """Patched ``negotiate_version`` that honours ``disable_minimum_supported_version_check``.

    The public SDK omits the ``disable_minimum_supported_version_check``
    guard, causing version negotiation to silently abort on servers running
    below v4.2. This patch mirrors the internal build which skips the
    minimum-version check when the flag is set.
    """
    try:
        # __call_api is name-mangled; use the explicit form since we are
        # defined outside the ApiClient class body.
        response = self._ApiClient__call_api(
            "/api/prism/unversioned/info",
            "OPTIONS",
            response_type="object",
            auth_settings=auth_settings,
        )
        if response is not None and "data" in response:
            server_version = response["data"]
            minimum_supported_version = "v4.2"

            if not getattr(
                self, "disable_minimum_supported_version_check", False
            ) and self.is_smaller_minor_version(
                self.get_version_details(server_version),
                self.get_version_details(minimum_supported_version),
            ):
                _patch_logger.warning(
                    "Server version %s is below minimum supported version %s. "
                    "Version negotiation will not be performed.",
                    server_version,
                    minimum_supported_version,
                )
                self.negotiated_version = None
                self.configuration.negotiation_completed = False
                return

            self.negotiated_version = self.perform_negotiation_between_versions(
                self.SDK_VERSION,
                server_version,
            )
            _patch_logger.info(
                "Negotiated version with the server: %s",
                self.negotiated_version,
            )
            self.configuration.negotiation_completed = True
        else:
            _patch_logger.error("Could not fetch supported versions from server")
            self.negotiated_version = None
            self.configuration.negotiation_completed = False
    except Exception as e:
        _patch_logger.error("Error during version negotiation: %s", e)
        self.negotiated_version = None
        self.configuration.negotiation_completed = False


def _snake_to_camel(name: str) -> str:
    """Convert a snake_case SDK method name to a camelCase operationId.

    Args:
        name: Snake-case string (e.g. ``"create_rsyslog_server"``).

    Returns:
        CamelCase string (e.g. ``"createRsyslogServer"``).
    """
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _default_method_name(operation: str, entity: str) -> str:
    """Return the conventional SDK method name for *operation* on *entity*.

    Single source of truth for the ``<operation>_<entity>[_by_id|s]``
    naming scheme that most Nutanix v4 SDK namespaces follow.  Entities
    whose SDK deviates from the convention override the default via an
    explicit ``<operation>_method_name`` entry in the entity map.

    Args:
        operation: One of ``"create"``, ``"update"``, ``"delete"``,
            ``"get"``, ``"list"``.
        entity: The ZTF entity name (used as the method-name stem).

    Returns:
        The default SDK method name for that operation/entity pair.
    """
    if operation == "create":
        return f"create_{entity}"
    if operation == "list":
        return f"list_{p.plural(entity)}"
    return f"{operation}_{entity}_by_id"


def _load_compat_map(
    path: Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Load the multi-namespace compatibility map.

    The map is structured as:
    ``{namespace: {operationId: {versions, schema, summary, ...}}}``

    Args:
        path: Path to the JSON file. Defaults to the standard location.

    Returns:
        The compatibility map dict (namespace -> operationId -> op_data).
    """
    global _compat_map_cache
    if _compat_map_cache is not None:
        return _compat_map_cache

    map_path = path or _COMPAT_MAP_PATH
    if not map_path.exists():
        _compat_map_cache = {}
        return _compat_map_cache

    with open(map_path, "rb") as fh:
        _compat_map_cache = orjson.loads(fh.read())

    return _compat_map_cache


class DomainEntityHandler:
    def __init__(
        self,
        entities: set,
        global_config_data: dict,
        entity_metadata_map: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the EntityCreator with a set of entities and configuration data.

        Args:
            entities: Set of entity names to initialize.
            global_config_data: Configuration data dictionary.
            entity_metadata_map: SDK metadata map (defaults to the
                module-level ``entity_map``).
        """
        self.entity_names: set = entities
        self.sdk_api_client_map: dict[str, Any] = {}
        self.sdk_config_map: dict[str, Any] = {}
        self.global_config_attrs = global_config_data["config"]
        self.entity_metadata_map: dict[str, Any] = (
            entity_metadata_map if entity_metadata_map else deepcopy(entity_map)
        )
        self.entity_cache: dict[tuple[Any, ...], Any] = {}
        self.logger = get_logger(
            __name__, log_file=self.global_config_attrs.get("logger_file", None)
        )
        # Optional per-handler overrides for task polling.  ``None`` lets
        # the monitor fall back to its own defaults (see
        # ``PcTaskMonitor``).  Both values are read from the global
        # config so operators can tune them per-PC without editing code.
        raw_task_timeout = self.global_config_attrs.get("task_timeout_seconds")
        raw_task_interval = self.global_config_attrs.get("task_check_interval_seconds")
        self.task_timeout_seconds: int | None = (
            int(raw_task_timeout) if raw_task_timeout is not None else None
        )
        self.task_check_interval_seconds: int | None = (
            int(raw_task_interval) if raw_task_interval is not None else None
        )
        self._initialize_entities()

    def _initialize_entities(self) -> None:
        """Initialize configuration, API clients, and CRUD maps for each entity."""
        self.entity_names.add("task")
        for entity_name in self.entity_names:
            if entity_name not in self.entity_metadata_map:
                raise ValueError(f"Unsupported entity: {entity_name!r}")
            self._initialize_config(entity_name)
            self._initialize_client(entity_name)
            self._initialize_entity_crud_mapping(entity_name)

    def _initialize_config(self, entity: str) -> None:
        """
        Initialize the "Configuration" class for a specific entity. We need only one instance of the Configuration class per SDK.

        :param entity: The entity name.
        """
        config_attrs = dict(self.global_config_attrs)  # shallow copy for safety

        entity_sdk_name = self.entity_metadata_map[entity]["sdk_name"]
        if entity_sdk_name not in self.sdk_config_map:
            entity_sdk = importlib.import_module(entity_sdk_name)
            config = entity_sdk.Configuration()
            # SDK Configuration.__init__ adds a StreamHandler with a UTC
            # formatter ("%(asctime)sZ").  Override it with ZTF's local-time
            # formatter so timestamps are consistent across ZTF and SDK logs.
            ztf_formatter = ColoredFormatter()
            config.logger_format = ztf_formatter
            sdk_logger = config.logger.get("package_logger")
            if sdk_logger is not None:
                for h in sdk_logger.handlers:
                    h.setFormatter(ztf_formatter)

            # Suppress verbose SDK rest.py error dumps on the console only.
            # The rest logger has no handlers of its own — it propagates to
            # the SDK package logger.  We add a filter to the parent's stream
            # handlers so file handlers still capture the full output.
            rest_name = f"{entity_sdk_name}.rest"
            if sdk_logger is not None:
                rest_filter = _RestLogFilter(rest_name)
                for h in sdk_logger.handlers:
                    if isinstance(h, logging.StreamHandler) and not isinstance(
                        h, logging.FileHandler
                    ):
                        h.addFilter(rest_filter)

            for attr, value in config_attrs.items():
                setattr(config, attr, value)
            self.sdk_config_map[entity_sdk_name] = config
            self.logger.debug(
                f"Initialized Configuration class for SDK: {entity_sdk_name!r}"
            )

    def _initialize_client(self, entity: str) -> None:
        """
        Initialize the API client for a specific entity. Each SDK should have only one API client instance.

        :param entity: The entity name.
        """
        entity_sdk_name = self.entity_metadata_map[entity]["sdk_name"]

        if entity_sdk_name not in self.sdk_api_client_map:
            entity_sdk = importlib.import_module(entity_sdk_name)
            kwargs = {"configuration": self.sdk_config_map[entity_sdk_name]}
            params = inspect.signature(
                entity_sdk.api_client.ApiClient.__init__
            ).parameters
            negotiation_enabled = (
                "allow_version_negotiation" in params
                and entity_sdk_name not in ["ntnx_iam_py_client"]
            )
            if negotiation_enabled:
                kwargs["allow_version_negotiation"] = True
                if entity_sdk_name not in _patched_api_clients:
                    entity_sdk.api_client.ApiClient.negotiate_version = (
                        _patched_negotiate_version
                    )
                    _patched_api_clients.add(entity_sdk_name)
                    self.logger.debug(
                        "Monkey-patched negotiate_version on %s.api_client.ApiClient",
                        entity_sdk_name,
                    )
            self.sdk_api_client_map[entity_sdk_name] = entity_sdk.api_client.ApiClient(
                **kwargs
            )
            if negotiation_enabled:
                self.sdk_api_client_map[
                    entity_sdk_name
                ].disable_minimum_supported_version_check = True
            if entity_sdk_name in ["ntnx_iam_py_client"]:
                self.logger.debug(
                    "Setting IAM SDK version to v4.1.b1 as negotiation is not supported for Hercules and below."
                )
                # For IAM version negotiation is not supported for Hercules and below. So I'll just set the version manually.
                # I can't install 4.0 or 4.1.b1 version of IAM because the latest v2 APIs require latest version of certifi and
                # the IAM v4.0 or v4.1.b1 versions have older certifi version requirement which causes conflict without any overlap.
                self.sdk_api_client_map[entity_sdk_name].negotiated_version = "v4.1.b1"
                self.sdk_api_client_map[
                    entity_sdk_name
                ].configuration.negotiation_completed = True
            self.logger.debug(f"Initialized API client for SDK: {entity_sdk_name!r}")

    def _initialize_entity_crud_mapping(self, entity: str) -> None:
        """
        Initialize the entity operation map for a specific entity.

        :param entity: The entity name.
        """
        if not self.entity_metadata_map[entity].get("api_class_path"):
            api_class_path = p.plural(entity) + "_api"
        else:
            api_class_path = self.entity_metadata_map[entity]["api_class_path"]
        if not self.entity_metadata_map[entity].get("api_class_name"):
            class_name = "".join(s.capitalize() for s in api_class_path.split("_"))
        else:
            class_name = self.entity_metadata_map[entity]["api_class_name"]

        api_class = self._get_class_from_path(
            f"{self.entity_metadata_map[entity]['sdk_name']}.api.{api_class_path}",
            class_name,
        )
        api_client = self.sdk_api_client_map[
            self.entity_metadata_map[entity]["sdk_name"]
        ]
        api_instance = api_class(api_client)
        # API instance is needed to call the API methods. (Eg: VmApi, ClusterApi, etc.)
        meta = self.entity_metadata_map[entity]
        meta["api_instance"] = api_instance
        for operation in ("create", "update", "delete", "get", "list"):
            key = f"{operation}_method_name"
            meta.setdefault(key, _default_method_name(operation, entity))
        self.logger.debug(f"Initialized entity operation map for entity: {entity!r}")

    @staticmethod
    def _get_class_from_path(path: str, class_name: str) -> Any:
        """
        Get a class from a given module path and class name.

        :param path: The module path.
        :param class_name: The class name.
        :return: The class object.
        """
        module = importlib.import_module(path)
        return getattr(module, class_name)

    def _get_api_client(self, entity: str) -> Any:
        return self.sdk_api_client_map[self.entity_metadata_map[entity]["sdk_name"]]

    def _get_parent_kwargs(
        self, entity: str, data: dict, *, pop: bool = False
    ) -> dict[str, Any]:
        """Extract parent ID keyword arguments for a sub-entity.

        Uses ``parent_id_param`` from entity_map to determine which
        parameter (if any) beyond ``extId`` / ``body`` is required by the
        SDK method, then pulls that value from *data*.

        When ``pop=True`` the consumed keys (both camelCase and
        snake_case variants) are removed from *data* so the caller can
        safely ``**data, **parent_kwargs`` without raising
        ``TypeError: got multiple values for keyword argument`` for
        sub-entities whose parent IDs already live at the top level of
        *data* (e.g. after ``Provider._build_handler_data`` merges
        ``params`` into ``data``).

        Args:
            entity: The entity name.
            data: Dict that may contain parent ID keys (e.g. ``clusterExtId``).
            pop: If True, remove the consumed keys from *data* in place.

        Returns:
            Dict of parent kwargs ready to pass to SDK methods.
        """
        parent_kwargs: dict[str, Any] = {}
        parent_id_param = self.entity_metadata_map[entity].get("parent_id_param")
        if not parent_id_param:
            return parent_kwargs

        snake_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", parent_id_param).lower()

        value: Any = None
        if parent_id_param in data:
            value = data[parent_id_param]
            if pop:
                data.pop(parent_id_param, None)
        elif snake_key in data:
            value = data[snake_key]
            if pop:
                data.pop(snake_key, None)
        elif pop:
            # No value found; still remove any present key so downstream
            # ``**data`` does not forward stale/None parent IDs.
            data.pop(parent_id_param, None)
            data.pop(snake_key, None)

        if value is not None:
            parent_kwargs[parent_id_param] = value
        return parent_kwargs

    def _build_method_kwargs(
        self,
        entity: str,
        operation: str,
        **data: Any,
    ) -> dict[str, Any]:
        """Build SDK method kwargs from method_params and data.

        Maps data keys (camelCase or snake_case) to param names expected
        by the SDK (entity_map method_params use camelCase).

        Args:
            entity: The entity name.
            operation: One of "create", "get", "update", "delete".
            **data: ext_id, body, parent IDs, etc.

        Returns:
            Dict of param_name -> value for the SDK call.
        """
        method_params = (
            self.entity_metadata_map.get(entity, {})
            .get("method_params", {})
            .get(operation, [])
        )
        result: dict[str, Any] = {}

        def _camel_to_snake(name: str) -> str:
            return re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")

        for param in method_params:
            if param == "body":
                result["body"] = data.get("body")
            elif param.lower() == "extid":
                val = data.get("ext_id")
                result[param] = val if val is not None else data.get("extId")
            elif param.startswith("_"):
                result[param] = data.get(param)
            else:
                snake = _camel_to_snake(param)
                val = data.get(param)
                result[param] = val if val is not None else data.get(snake)

        if not method_params:
            # Fallback shape: the entity_map is missing method_params for
            # *operation*, so infer the primary key from the operation
            # family and forward everything else verbatim.  The three
            # branches used to duplicate ~4 lines each; they collapse to
            # a table lookup plus a single passthrough loop.
            if operation in ("create", "update"):
                primary = "body"
                exclusions: set[str] = {"body"}
                result["body"] = data.get("body")
            elif operation in ("get", "delete"):
                primary = "extId"
                exclusions = {"ext_id", "extId"}
                result["extId"] = data.get("ext_id") or data.get("extId")
            else:
                primary = ""
                exclusions = set()
            if primary:
                for k, v in data.items():
                    if k not in exclusions:
                        result[k] = v

        return {k: v for k, v in result.items() if v is not None}

    def _get_readonly_fields_for_entity_operation(
        self,
        entity: str,
        operation: str,
    ) -> set:
        """Return set of request body field names marked readOnly for this operation.

        Uses the compatibility map schema.request for the entity's operation.
        """
        meta = self.entity_metadata_map.get(entity, {})
        namespace = meta.get("namespace")
        if not namespace:
            return set()
        method_key = "update" if operation == "update" else "create"
        method_name = meta.get(f"{method_key}_method_name")
        if not method_name:
            return set()
        operation_id = _snake_to_camel(method_name)
        compat = _load_compat_map()
        ns_ops = compat.get(namespace, {})
        op_data = ns_ops.get(operation_id)
        if not op_data:
            return set()
        request_schema = op_data.get("schema", {}).get("request", {})
        return {
            name
            for name, field_schema in request_schema.items()
            if field_schema.get("readOnly", False)
        }

    def _prepare_update_body(
        self,
        get_response: Any,
        user_updates: dict[str, Any],
        api_client: Any,
        readonly_fields: set | None = None,
    ) -> dict[str, Any]:
        """Prepare PUT body: strip read-only from GET response, deep-merge user updates.

        Args:
            get_response: Full GET API response (wrapper with .data).
            user_updates: User-provided update body.
            api_client: SDK API client for serialization.
            readonly_fields: Schema-derived readOnly field names to strip.

        Returns:
            Merged dict ready for PUT.
        """
        response_dict = api_client._ApiClient__sanitize_for_serialization(get_response)
        if isinstance(response_dict, dict) and "data" in response_dict:
            current_entity = response_dict["data"]
        else:
            current_entity = response_dict
        if not isinstance(current_entity, dict):
            current_entity = {}

        system_readonly = {
            "extId",
            "tenantId",
            "links",
            "metadata",
            "$objectType",
            "$reserved",
            "$unknownFields",
        }
        to_strip = system_readonly | (readonly_fields or set())
        for field in to_strip:
            current_entity.pop(field, None)

        merged = deep_merge(dict(current_entity), user_updates)

        def _strip_empty_strings(d: dict[str, Any]) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for k, v in d.items():
                if isinstance(v, dict):
                    cleaned = _strip_empty_strings(v)
                    if cleaned:
                        out[k] = cleaned
                elif isinstance(v, str) and v == "":
                    continue
                elif v is not None:
                    out[k] = v
            return out

        return _strip_empty_strings(merged)

    def _is_etag_required(self, entity: str, operation: str) -> bool:
        """Check whether an operation on *entity* requires an If-Match etag.

        Uses the new ``etag_required`` dict when available, falling back to
        the legacy ``delete_etag_required`` boolean for backwards compatibility.

        Args:
            entity: The entity name.
            operation: One of ``"update"`` or ``"delete"``.

        Returns:
            True if etag is required.
        """
        meta = self.entity_metadata_map[entity]
        etag_map = meta.get("etag_required")
        if isinstance(etag_map, dict):
            return etag_map.get(operation, False)
        # Legacy fallback
        if operation == "delete":
            return bool(meta.get("delete_etag_required", False))
        # update always required etag in old code path
        return True

    def _get_target_version(self, entity: str) -> float | None:
        """Determine the negotiated API version for the entity's SDK.

        Parses the SDK client's ``negotiated_version`` (e.g. ``"v4.1.b1"``,
        ``"v4.2"``) into a float (e.g. ``4.1``, ``4.2``).

        Args:
            entity: The entity name.

        Returns:
            Version as float (e.g. ``4.2``), or *None* if unavailable.
        """
        sdk_name = self.entity_metadata_map[entity].get("sdk_name", "")
        api_client = self.sdk_api_client_map.get(sdk_name)
        if not api_client:
            return None
        version_str = getattr(api_client, "negotiated_version", None)
        if not version_str or not isinstance(version_str, str):
            return None
        # Parse "v4.1.b1" or "v4.2" -> 4.1 or 4.2
        match = re.match(r"v?(\d+\.\d+)", version_str)
        if match:
            return float(match.group(1))
        return None

    def _negotiate_schema(self, entity: str, method_name: str, body: Any) -> Any:
        """Filter request body based on target PC version's schema compatibility.

        Looks up the ``multi_namespace_compatibility_map`` for the entity's
        namespace and the operation's camelCase operationId.  Recursively walks
        the body dict and strips fields that are not present in the target
        PC version.

        Args:
            entity: The entity name.
            method_name: SDK method name (e.g. ``"create_rsyslog_server"``).
            body: Request body dict (will NOT be mutated -- a filtered copy is
                returned).

        Returns:
            Filtered body dict, or the original body unchanged if schema
            negotiation is not applicable.
        """
        if not isinstance(body, dict):
            return body

        namespace = self.entity_metadata_map[entity].get("namespace")
        if not namespace:
            return body

        target_version = self._get_target_version(entity)
        if target_version is None:
            return body

        compat_map = _load_compat_map()
        if not compat_map:
            return body

        ns_ops = compat_map.get(namespace, {})
        operation_id = _snake_to_camel(method_name)
        op_data = ns_ops.get(operation_id)
        if not op_data:
            return body

        schema = op_data.get("schema", {})
        request_schema = schema.get("request", {})
        if not request_schema:
            return body

        return self._filter_body_by_version(
            body, request_schema, target_version, method_name
        )

    def _filter_body_by_version(
        self,
        body: dict,
        schema: dict[str, Any],
        target_version: float,
        context: str,
    ) -> dict:
        """Recursively filter body fields not supported in *target_version*.

        Also strips ``readOnly`` fields (response-only) and handles
        ``oneOf`` variants by matching on ``$objectType``.

        Args:
            body: The request body dict.
            schema: Versioned schema from the compatibility map.
            target_version: Target PC API version (e.g. ``4.0``).
            context: Operation context string for logging.

        Returns:
            A new dict with unsupported / readOnly fields removed.
        """
        filtered: dict = {}
        for key, value in body.items():
            field_schema = schema.get(key)
            if field_schema is None:
                # Field not in schema at all -- pass through unchanged
                filtered[key] = value
                continue

            # Skip readOnly fields in request bodies
            if field_schema.get("readOnly", False):
                self.logger.debug(
                    f"[schema-neg] Stripping readOnly field {key!r} from {context}"
                )
                continue

            supported_versions = field_schema.get("versions", [])
            if supported_versions and target_version not in supported_versions:
                self.logger.warning(
                    f"[schema-neg] Stripping field {key!r} from {context}: "
                    f"not supported in v{target_version} "
                    f"(available in {supported_versions})"
                )
                continue

            # -- oneOf variants: match by $objectType ------------------------
            variants = field_schema.get("variants")
            if variants and isinstance(value, dict):
                obj_type = value.get("$objectType", "")
                matched_props: dict[str, Any] | None = None
                for _vname, vdata in variants.items():
                    if obj_type and vdata.get("object_type", "") in obj_type:
                        matched_props = vdata.get("properties", {})
                        break
                if matched_props:
                    filtered[key] = self._filter_body_by_version(
                        value,
                        matched_props,
                        target_version,
                        f"{context}.{key}",
                    )
                else:
                    # Cannot determine variant -- pass through unchanged
                    filtered[key] = value
                continue

            # -- nested object properties ------------------------------------
            nested_props = field_schema.get("properties", {})
            if isinstance(value, dict) and nested_props:
                filtered[key] = self._filter_body_by_version(
                    value,
                    nested_props,
                    target_version,
                    f"{context}.{key}",
                )
            elif isinstance(value, list) and nested_props:
                filtered[key] = [
                    self._filter_body_by_version(
                        item,
                        nested_props,
                        target_version,
                        f"{context}.{key}[]",
                    )
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                filtered[key] = value

        return filtered

    def _get_tag(
        self, entity: str, ext_id: str, api_client, **parent_kwargs: Any
    ) -> str:
        """Fetch the etag for an entity, forwarding parent ID params.

        Args:
            entity: The entity name.
            ext_id: The entity's external ID.
            api_client: The SDK API client.
            **parent_kwargs: Parent ID parameters (e.g. ``clusterExtId``).

        Returns:
            The etag string.

        Raises:
            Exception: On API failure.
        """
        try:
            entity_obj = self.get_entity_by_ext_id(entity, ext_id, **parent_kwargs)
            return api_client.get_etag(entity_obj)
        except Exception as e:
            self.logger.error(
                f"Error while getting e-tag for {entity!r} with ext_id: {ext_id}"
            )
            raise Exception(raise_api_exception(e)) from e

    def _monitor_task(self, ext_id: str) -> dict:
        task_monitor = PcTaskMonitor(
            self.sdk_api_client_map["ntnx_prism_py_client"],
            ext_id,
            timeout_seconds=self.task_timeout_seconds,
            check_interval_seconds=self.task_check_interval_seconds,
        )
        completed, status, response_data = task_monitor.monitor()
        response_data_dict: dict[str, Any] = response_data.to_dict()  # type: ignore[attr-defined]
        response_data_dict = snake_to_camel(response_data_dict)
        self.logger.info(f"Task {status} (completed={completed})")
        self.logger.debug(
            f"Task response: {strip_internal_attributes(deepcopy(response_data_dict))}"
        )
        if status != TaskStatus.SUCCEEDED and status != "Timed out":
            exception_msg = f"Error: {[error_message.message for error_message in response_data.error_messages]}"  # type: ignore[attr-defined]
            if response_data.legacy_error_message:  # type: ignore[attr-defined]
                exception_msg += (
                    f" Legacy error message: {response_data.legacy_error_message}"  # type: ignore[attr-defined]
                )
            raise Exception(exception_msg)
        if status == "Timed out":
            self.logger.warning(
                f"Task timed out: {strip_internal_attributes(deepcopy(response_data_dict))}"
            )
        return response_data_dict

    def _extract_ext_id_from_task(
        self,
        response_data: dict[str, Any],
        entity: str,
        method_name: str,
    ) -> str | None:
        """Extract the entity ext_id from a completed task response.

        Checks ``entitiesAffected``, then top-level ``extId`` /
        ``{entity}ExtId`` / ``{entity}extId`` keys.

        Args:
            response_data: Serialised task response dict.
            entity: Entity type name (used to build key variants).
            method_name: API method name (for log messages).

        Returns:
            The extracted ext_id string, or *None* if not found.
        """
        ext_id_keys = [f"{entity}ExtId", "extId", f"{entity}extId"]

        affected = response_data.get("entitiesAffected") or []
        if affected:
            first = affected[0] if isinstance(affected[0], dict) else {}
            for key in ext_id_keys:
                if value := first.get(key):
                    return str(value)

        for key in ext_id_keys:
            if key in response_data:
                return str(response_data[key]).split("=:")[-1]

        self.logger.debug(
            "Task response missing ext_id: %s",
            strip_internal_attributes(deepcopy(response_data)),
        )
        self.logger.warning(
            "Could not extract ext_id from task response for %r", method_name
        )
        return None

    def _execute_method_with_task_monitor(
        self,
        api_instance: Any,
        method_name: str,
        entity: str,
        *args: Any,
        resource_name: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        label = f"{entity}/{resource_name}" if resource_name else entity
        method = getattr(api_instance, method_name)
        body = kwargs.pop("body", None)
        api_client = self._get_api_client(entity) if entity else None

        try:
            if body is not None and api_client is not None:
                response = call_api_with_body(method, body, api_client, **kwargs)
            else:
                response = method(*args, **kwargs)
        except Exception as e:
            raise e
        if not response or not hasattr(response, "data"):
            self.logger.debug(
                "Empty or data-less response for %r on %s (likely 202 Accepted)",
                method_name,
                label,
            )
            return None
        ext_id = getattr(response.data, "ext_id", None)
        object_type = getattr(response.data, "_object_type", None) or None

        if object_type == "prism.v4.config.TaskReference":
            if ext_id is None:
                raise Exception(f"Task reference has no ext_id for {method_name!r}")
            response_data = self._monitor_task(ext_id)
            entity_ext_id = self._extract_ext_id_from_task(
                response_data, entity, method_name
            )
        else:
            entity_ext_id = ext_id or getattr(response.data, f"{entity}_ext_id", None)
            if response.data and hasattr(response.data, "to_dict"):
                response_data = response.data.to_dict()
                response_data = snake_to_camel(response_data)
                response_data = strip_internal_attributes(response_data)
                self.logger.debug(f"Response data: {redact_secrets(response_data)}")
            else:
                self.logger.debug(f"Response data: {response.data!r}")

        if entity_ext_id:
            self.logger.info(f"'{label}' completed with ext_id: {entity_ext_id}")
        return entity_ext_id

    def create(
        self, entity: str, data: dict, resource_name: str | None = None
    ) -> str | None:
        """Create an entity instance.

        Args:
            entity: The entity name.
            data: The body and parameters for creating the entity.
            resource_name: User-defined resource name for logging.

        Returns:
            The external ID of the created entity.
        """
        resource_name = resource_name or data.get("resource_name")
        label = f"{entity}/{resource_name}" if resource_name else entity
        self.logger.info(f"Creating entity '{label}'")
        self.logger.debug(f"Data: {redact_secrets(data)}")

        data = deepcopy(data)

        if entity not in self.entity_metadata_map:
            self.logger.error(f"Unsupported entity: {entity}")
            raise ValueError(f"Unsupported entity: {entity}")

        create_supported = self.entity_metadata_map[entity].get(
            "create_supported", "True"
        )
        if isinstance(create_supported, str):
            create_supported = create_supported.strip().lower() in ("true", "1", "yes")
        if not create_supported:
            raise ValueError(f"Create operation not supported for entity: {entity!r}.")

        create_params = (
            self.entity_metadata_map[entity].get("method_params", {}).get("create", [])
        )
        has_body = "body" in create_params

        if has_body:
            if "body" not in data:
                self.logger.error(f"Missing 'body' key in data for entity: {entity!r}")
                raise ValueError(f"Missing 'body' key in data for entity: {entity!r}")
            body = data.pop("body")
        else:
            body = data.pop("body", None)

        data.pop("resource_name", None)
        data.pop("params", None)  # params already merged by Provider
        data.pop("rules", None)
        data.pop("operations", None)
        data.pop("ext_id", None)

        if has_body:
            try:
                if self.entity_metadata_map[entity].get("filter_format"):
                    filter_format = self.entity_metadata_map[entity]["filter_format"]
                    if filter_format:
                        try:
                            _filter = filter_format.format(**body)
                        except KeyError as e:
                            self.logger.error(
                                f"Error in filter format for entity: {entity!r}. Missing key: {e}"
                            )
                            raise KeyError(
                                f"Error in filter format for entity: {entity!r}. Missing key: {e}"
                            ) from e

                        existing_entity, _filter = self.get_entity_by_identifier(
                            entity, _filter=_filter, **data
                        )
                        if existing_entity:
                            self.logger.info(
                                f"'{label}' already exists with filter {_filter!r}. Skipping creation."
                            )
                            return existing_entity.ext_id
                    else:
                        self.logger.warning(
                            f"No filter format defined for '{label}' to check if it exists"
                        )
            except Exception as e:
                self.logger.error(f"Error while checking if '{label}' already exists")
                raise Exception(raise_api_exception(e)) from e

        api_instance = self.entity_metadata_map[entity]["api_instance"]
        create_method_name = self.entity_metadata_map[entity]["create_method_name"]

        if has_body and body is not None:
            body = self._negotiate_schema(entity, create_method_name, body)

        create_kwargs = self._build_method_kwargs(entity, "create", body=body, **data)
        try:
            ext_id = self._execute_method_with_task_monitor(
                api_instance,
                create_method_name,
                entity,
                resource_name=resource_name,
                **create_kwargs,
            )
            if not ext_id:
                raise Exception(f"Failed to create '{label}'")
            return ext_id
        except Exception as e:
            err_info = raise_api_exception(e)
            self.logger.error(f"Error creating '{label}' via {create_method_name!r}")
            if getattr(e, "status", None) == 400:
                err_body = getattr(e, "body", "") or ""
                if "already exists" in err_body.lower():
                    self.logger.error(
                        "Hint: '%s' may already exist on the cluster. "
                        "Use 'ztf import' to bring it under management.",
                        label,
                    )
            raise Exception(err_info) from e

    def update(
        self, entity: str, data: dict, resource_name: str | None = None
    ) -> str | None:
        """Update an entity instance.

        Parent ID parameters (e.g. ``clusterExtId``) are extracted from
        *data* automatically and forwarded to both the etag fetch and the
        SDK update call.

        Args:
            entity: The entity name.
            data: Dict with ``body``, ``ext_id``/``extId``, and optional
                parent ID keys.
            resource_name: User-defined resource name for logging.

        Returns:
            The external ID of the updated entity.

        Raises:
            ValueError: If entity is unsupported or required keys are missing.
        """
        resource_name = resource_name or data.get("resource_name")
        label = f"{entity}/{resource_name}" if resource_name else entity
        self.logger.info(f"Updating entity '{label}'")
        self.logger.debug(f"Data: {redact_secrets(data)}")

        if entity not in self.entity_metadata_map:
            self.logger.error(f"Unsupported entity: {entity}")
            raise ValueError(f"Unsupported entity: {entity}")

        data = deepcopy(data)
        update_supported = self.entity_metadata_map[entity].get(
            "update_supported", "True"
        )
        if isinstance(update_supported, str):
            update_supported = update_supported.strip().lower() in ("true", "1", "yes")
        if not update_supported:
            raise ValueError(
                f"Update operation not supported for entity: {entity!r}. "
                "Please Delete the resource and create a new one."
            )

        update_params = (
            self.entity_metadata_map[entity].get("method_params", {}).get("update", [])
        )
        has_body = "body" in update_params

        if has_body and "body" not in data:
            self.logger.error(f"Missing 'body' key in data for entity: {entity!r}")
            raise ValueError(f"Missing 'body' key in data for entity: {entity!r}")
        if "ext_id" not in data and "extId" not in data:
            self.logger.error(f"Missing 'ext_id' key in data for entity: {entity!r}")
            raise ValueError(f"Missing 'ext_id' key in data for entity: {entity!r}")

        self.logger.info(f"Updating '{label}'")
        self.logger.debug(f"Update payload for '{label}': {redact_secrets(data)}")
        init_body = data.pop("body", None)
        ext_id = data.pop("ext_id", "") or data.pop("extId", "")
        data.pop("resource_name", None)
        data.pop("params", None)  # params already merged by Provider
        data.pop("rules", None)
        data.pop("operations", None)

        # pop=True removes the parent-id key(s) from *data* so the later
        # ``**data, **parent_kwargs`` unpacks cannot collide for
        # sub-entities (e.g. clusterExtId) whose parent ID was merged in
        # by Provider._build_handler_data.
        parent_kwargs = self._get_parent_kwargs(entity, data, pop=True)

        api_instance = self.entity_metadata_map[entity]["api_instance"]
        update_method_name = self.entity_metadata_map[entity]["update_method_name"]
        api_client = self._get_api_client(entity)

        if has_body and init_body is not None:
            get_method_name = self.entity_metadata_map[entity]["get_method_name"]

            # PUT semantics: GET current, strip readOnly, merge user body, PUT
            get_kwargs = self._build_method_kwargs(
                entity, "get", ext_id=ext_id, **data, **parent_kwargs
            )
            get_method = getattr(api_instance, get_method_name)
            get_response = get_method(**get_kwargs)

            readonly_fields = self._get_readonly_fields_for_entity_operation(
                entity, "update"
            )
            merged_body = self._prepare_update_body(
                get_response, init_body, api_client, readonly_fields
            )
            merged_body = self._negotiate_schema(
                entity, update_method_name, merged_body
            )
        else:
            merged_body = init_body

        update_kwargs = self._build_method_kwargs(
            entity,
            "update",
            ext_id=ext_id,
            body=merged_body,
            **data,
            **parent_kwargs,
        )

        # Per-call If-Match via the SDK ``if_match`` kwarg (the SDK maps
        # it to the ``If-Match`` header for this single request).  This
        # removes the need for a per-SDK lock that previously serialized
        # every etag-guarded update through the shared
        # ``ApiClient.__default_headers`` dict.
        if self._is_etag_required(entity, "update"):
            try:
                update_kwargs["if_match"] = self._get_tag(
                    entity, ext_id, api_client, **parent_kwargs
                )
            except Exception as e:
                self.logger.error(
                    f"Error getting e-tag for '{label}' (ext_id: {ext_id})"
                )
                self.logger.error(raise_api_exception(e))
                raise e

        try:
            _ = self._execute_method_with_task_monitor(
                api_instance,
                update_method_name,
                entity,
                resource_name=resource_name,
                **update_kwargs,
            )
            return ext_id
        except Exception as e:
            self.logger.error(f"Error updating '{label}' via {update_method_name!r}")
            raise Exception(raise_api_exception(e)) from e

    def delete(
        self,
        entity: str,
        ext_id: str,
        resource_name: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Delete an entity by external ID.

        For sub-entities (e.g. ``rsyslog_server``), the caller must pass
        the parent ID as a keyword argument (e.g.
        ``clusterExtId="abc-123"``).

        Args:
            entity: The entity name.
            ext_id: The entity's external ID.
            resource_name: User-defined resource name for logging.
            **kwargs: Parent ID parameters required by the SDK method.

        Returns:
            The external ID of the deleted entity.

        Raises:
            ValueError: If entity is unsupported or delete not supported.
        """
        label = f"{entity}/{resource_name}" if resource_name else entity
        if entity not in self.entity_metadata_map:
            self.logger.error(f"Unsupported entity: {entity}")
            raise ValueError(f"Unsupported entity: {entity}")

        delete_supported = self.entity_metadata_map[entity].get(
            "delete_supported", "True"
        )
        if isinstance(delete_supported, str):
            delete_supported = delete_supported.strip().lower() in ("true", "1", "yes")
        if not delete_supported:
            raise ValueError(f"Delete operation not supported for entity: {entity!r}.")

        self.logger.info(f"Deleting '{label}' (ext_id: {ext_id})")
        api_instance = self.entity_metadata_map[entity]["api_instance"]
        delete_method_name = self.entity_metadata_map[entity]["delete_method_name"]

        delete_kwargs = self._build_method_kwargs(
            entity, "delete", ext_id=ext_id, **kwargs
        )

        # Per-call If-Match via ``if_match`` kwarg (no shared-header
        # mutation, so concurrent deletes on the same SDK no longer
        # serialize).
        if self._is_etag_required(entity, "delete"):
            api_client = self._get_api_client(entity)
            try:
                delete_kwargs["if_match"] = self._get_tag(
                    entity, ext_id, api_client, **kwargs
                )
            except Exception as e:
                self.logger.error(
                    f"Error getting e-tag for '{label}' (ext_id: {ext_id})"
                )
                raise Exception(raise_api_exception(e)) from e

        try:
            _ = self._execute_method_with_task_monitor(
                api_instance,
                delete_method_name,
                entity,
                resource_name=resource_name,
                **delete_kwargs,
            )
            return ext_id
        except Exception as e:
            self.logger.error(f"Error deleting '{label}' via {delete_method_name!r}")
            raise Exception(raise_api_exception(e)) from e

    def run_operation(
        self,
        entity: str,
        operation_data: dict[str, Any],
        resource_name: str | None = None,
    ) -> str | None:
        """Execute an operation on a resource.

        All required parameters (including resource IDs) must be
        provided explicitly in ``operation_data["params"]``.

        Args:
            entity: The entity name.
            operation_data: Dict with ``type``, optional ``params``,
                optional ``body``.
            resource_name: User-defined resource name for logging.

        Returns:
            The ext_id returned by the SDK operation, or ``None``.
        """
        label = f"{entity}/{resource_name}" if resource_name else entity
        if "type" not in operation_data:
            raise ValueError(f"Operation 'type' not specified for '{label}'")

        operation_name = operation_data["type"]

        ops_list = self.entity_metadata_map.get(entity, {}).get("operations", [])
        if operation_name not in ops_list:
            raise ValueError(
                f"Unsupported operation: {operation_name!r} for '{label}'. "
                f"Available: {ops_list}"
            )

        api_instance = self.entity_metadata_map[entity]["api_instance"]

        op_kwargs: dict[str, Any] = dict(operation_data.get("params", {}))

        if "body" in operation_data:
            op_kwargs["body"] = operation_data["body"]

        self.logger.info(f"Running operation {operation_name!r} on '{label}'")
        self.logger.debug(f"Operation kwargs: {redact_secrets(op_kwargs)}")
        self.logger.debug(
            f"Operation body: {redact_secrets(operation_data.get('body', {}))}"
        )

        try:
            return self._execute_method_with_task_monitor(
                api_instance,
                operation_name,
                entity,
                resource_name=resource_name,
                **op_kwargs,
            )
        except Exception as e:
            self.logger.error(
                f"Error executing operation {operation_name!r} on '{label}'"
            )
            raise Exception(raise_api_exception(e)) from e

    #: Upper bound on pagination loop iterations.  At the SDK default
    #: page size of 50 this allows up to 50 000 entities per list call,
    #: which is well beyond realistic Prism Central limits and still
    #: guarantees termination if the server keeps returning stale
    #: ``total_available_results`` counts.
    _MAX_PAGINATION_PAGES: int = 1000

    def list_entities(
        self, entity: str, _filter: str | None = None, **kwargs
    ) -> list[Any]:
        """Return every entity row, transparently paginating the SDK call.

        A forward-progress guard and hard page cap ensure termination even
        when the server returns an inconsistent ``total_available_results``
        or keeps handing back the same page.

        Args:
            entity: The entity name.
            _filter: Optional filter string for the list method.

        Returns:
            List of entity objects across all pages.
        """
        list_method_name = self.entity_metadata_map[entity]["list_method_name"]
        api_instance = self.entity_metadata_map[entity]["api_instance"]
        list_method = getattr(api_instance, list_method_name)

        list_kwargs = dict(kwargs)
        if _filter is not None:
            list_kwargs["_filter"] = _filter
        initial_response = list_method(**list_kwargs)
        full_list_count = initial_response.metadata.total_available_results
        full_list = list(initial_response.data or [])
        page = 1
        while full_list and len(full_list) < full_list_count:
            if page >= self._MAX_PAGINATION_PAGES:
                self.logger.warning(
                    "Pagination safety cap (%d pages) hit for '%s'; "
                    "returning %d of %d reported rows. The server's "
                    "total_available_results may be stale.",
                    self._MAX_PAGINATION_PAGES,
                    entity,
                    len(full_list),
                    full_list_count,
                )
                break
            page_kwargs = dict(list_kwargs)
            page_kwargs["_page"] = page
            next_page_data = list_method(**page_kwargs).data
            if not next_page_data:
                break
            before = len(full_list)
            full_list.extend(next_page_data)
            if len(full_list) == before:
                # Forward-progress guard: page returned rows but the
                # accumulator did not grow (e.g. SDK handed back an
                # empty iterable masquerading as truthy).  Bail rather
                # than loop forever.
                self.logger.warning(
                    "Pagination made no forward progress for '%s' at page %d; "
                    "returning %d rows accumulated so far.",
                    entity,
                    page,
                    len(full_list),
                )
                break
            page += 1
        return full_list

    def get_entity_by_ext_id(self, entity: str, ext_id: str, **kwargs: Any) -> Any:
        """Get an entity by its external ID.

        For sub-entities the caller must pass parent ID kwargs (e.g.
        ``clusterExtId="abc-123"``).

        Args:
            entity: The entity name.
            ext_id: The external ID.
            **kwargs: Parent ID parameters required by the SDK get method.

        Returns:
            The entity data object.
        """
        get_method_name = self.entity_metadata_map[entity]["get_method_name"]
        api_instance = self.entity_metadata_map[entity]["api_instance"]
        get_method = getattr(api_instance, get_method_name)
        get_kwargs = self._build_method_kwargs(entity, "get", ext_id=ext_id, **kwargs)
        return get_method(**get_kwargs).data

    def get_entity(self, entity: str, **kwargs: Any) -> Any:
        """Get an entity by its external ID or other identifiers.

        When only ``ext_id`` / ``extId`` is provided (plus optional parent
        kwargs), delegates to :meth:`get_entity_by_ext_id`.  Otherwise the
        full *kwargs* are forwarded directly to the SDK get method.

        Args:
            entity: The entity name.
            **kwargs: Must include ``ext_id`` or ``extId``.  May include
                parent ID params (e.g. ``clusterExtId``).

        Returns:
            The entity data object.
        """
        ext_id = kwargs.pop("ext_id", None) or kwargs.pop("extId", None)
        if ext_id is not None:
            return self.get_entity_by_ext_id(entity, ext_id, **kwargs)

        get_method_name = self.entity_metadata_map[entity]["get_method_name"]
        api_instance = self.entity_metadata_map[entity]["api_instance"]
        get_method = getattr(api_instance, get_method_name)
        return get_method(**kwargs)

    def sanitize_entity_data(self, entity: str, data) -> dict:
        """
        Sanitize the entity data by converting returned object to a dictionary and stripping internal attributes.

        :param entity: The entity name.
        :param data: The data to sanitize.
        :return: The sanitized data.
        """
        if not data:
            self.logger.error(f"Data is None for entity: {entity!r}")
            raise ValueError(f"Data is None for entity: {entity!r}")

        if hasattr(data, "data"):
            if data.data is None:
                self.logger.error(f"Data has no content for entity: {entity!r}")
                raise ValueError(f"Data has no content for entity: {entity!r}")
            data = data.data
        api_client = self._get_api_client(entity)
        return api_client._ApiClient__sanitize_for_serialization(data)

    def get_entity_by_identifier(
        self, entity: str, _filter: str | None, **kwargs
    ) -> tuple[Any | None, str | None]:
        """
        Get an entity by its identifier using the filter format defined in the entity map.

        :param entity: The entity name.
        :param _filter: filter string to use for the entity.
        :param kwargs: The identifier attributes to be used in the filter.
        :return: The entity object and filter used if found, otherwise None.
        """
        # There are two ways to go about this
        # 1. Through list_entities with filter
        # 2. Through get_entity_<> with extid or any other unique identifier
        # So I am assuming if _filter is provided, we will use list_entities
        #
        # Cache keys are typed tuples instead of joined strings: collisions
        # that could arise from underscore-bearing entity names or filter
        # values (e.g. ``f"{entity}_{filter}"`` rendering identically for
        # two distinct (entity, filter) pairs) are eliminated by carrying
        # a discriminator (``"extId"`` vs ``"filter"``) and the structured
        # payload itself.
        if not _filter:
            if not kwargs.get("extId") and not kwargs.get("ext_id"):
                raise ValueError(
                    f"Either extId or ext_id must be provided for entity: {entity!r}"
                )
            # Sort by key name (not full item) so unsortable/mixed value
            # types don't break the key; hash unhashable values via
            # ``repr`` so the final tuple is always hashable.
            cache_key: tuple[Any, ...] = (
                entity,
                "extId",
                tuple(
                    (
                        k,
                        v
                        if isinstance(v, (str, int, float, bool, type(None)))
                        else repr(v),
                    )
                    for k, v in sorted(kwargs.items(), key=lambda kv: kv[0])
                ),
            )
            if cache_key not in self.entity_cache:
                entity_obj = self.get_entity_by_ext_id(entity, kwargs["ext_id"])
                self.entity_cache[cache_key] = entity_obj
            return self.entity_cache[cache_key], kwargs["ext_id"]
        cache_key = (entity, "filter", _filter)
        if cache_key in self.entity_cache:
            return self.entity_cache[cache_key], _filter

        try:
            entities = self.list_entities(entity, _filter=_filter, **kwargs)
            if entities:
                self.entity_cache[cache_key] = entities[0]
                return self.entity_cache[cache_key], _filter
            return None, _filter
        except Exception as e:
            raise e
