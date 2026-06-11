"""Generate per-entity YAML example configs and Markdown reference docs.

Reads ``entity_map`` and ``multi_namespace_metadata_map.json``, then
writes:

- ``config/examples/<namespace>/<entity>.yml``  -- concise YAML examples
- ``config/examples/<namespace>/<entity>.md``   -- full Markdown reference

CLI usage::

    ztf examples             # all namespaces
    ztf examples --namespace clustermgmt
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENTITY_MAP_PATH = _PROJECT_ROOT / "ztf" / "entity_wrapper" / "entity_map.py"
_COMPAT_MAP_PATH = (
    _PROJECT_ROOT / "ztf" / "entity_wrapper" / "multi_namespace_metadata_map.json"
)
# Default output is relative to the current working directory so that
# installed packages don't write into site-packages.
_OUTPUT_DIR = Path("examples")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOCS_BASE = "https://developers.nutanix.com/api-reference"
_SKIP_FIELDS = frozenset(
    {
        "tenantId",
        "links",
        "$objectType",
        "$reserved",
        "$unknownFields",
        "$fv",
    }
)
_SKIP_ENUM_VALUES = frozenset({"$UNKNOWN", "$REDACTED"})
_METHOD_KEYS = ("create", "update", "delete", "list", "get")
_MAX_YAML_DEPTH = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _camel_to_snake(name: str) -> str:
    """Convert PascalCase / camelCase to snake_case."""
    return _CAMEL_RE.sub("_", name).lower()


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase operationId."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _load_entity_map() -> dict[str, Any]:
    """Parse ``entity_map`` dict from the source file via AST."""
    src = _ENTITY_MAP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "entity_map":
                    return ast.literal_eval(node.value)  # type: ignore[arg-type]
    msg = "entity_map not found in source"
    raise RuntimeError(msg)


def _load_compat_map() -> dict[str, Any]:
    """Load the compatibility map JSON."""
    with open(_COMPAT_MAP_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _get_op_data(
    compat: dict[str, Any],
    namespace: str,
    method_name: str,
) -> dict[str, Any] | None:
    """Look up an operation in the compat map by snake_case method name."""
    if not method_name:
        return None
    op_id = _snake_to_camel(method_name)
    return compat.get(namespace, {}).get(op_id)


def _filter_enum(values: list[str]) -> list[str]:
    """Remove $UNKNOWN / $REDACTED from enum value lists."""
    return [v for v in values if v not in _SKIP_ENUM_VALUES]


_ODATA_PARAM_RE = re.compile(r"\$(?:filter|orderby|select)=(.+?)(?:&|$)")


def _extract_odata_expr(example_url: str) -> str:
    """Extract the OData expression from a full example URL.

    Args:
        example_url: Full URL like
            ``https://...?$filter=name eq 'x'``.

    Returns:
        Just the expression, or the original string if no known
        OData parameter is found.
    """
    match = _ODATA_PARAM_RE.search(example_url)
    return match.group(1).strip() if match else example_url


# ---------------------------------------------------------------------------
# Cross-entity reference detection
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_REF_SUFFIXES = ("ExtId", "ExtID", "Reference", "Uuid")
_REF_PREFIXES = frozenset(
    {
        "primary",
        "secondary",
        "source",
        "target",
        "owner",
        "new",
        "current",
        "parent",
        "origin",
        "destination",
        "ingress",
        "egress",
    }
)

# Definitive field-name -> entity mapping for cases the heuristic cannot
# resolve (entity name doesn't match after suffix/prefix stripping).
# Maintained as a one-time effort; add entries when new entities are added.
_FIELD_TO_ENTITY_MAP: dict[str, str] = {
    # vmm
    "imageExtId": "vmm_image",
    "diskExtId": "clustermgmt_disk",
    "externalRepositoryExtId": "external_repository",
    "volumeGroupExtId": "volume_group",
    # networking
    "networkExtId": "subnet",
    # files
    "mountTargetExtId": "file_server_mount_target",
    # clustermgmt
    "hostExtId": "cluster_host",
    # iam
    "dirSvcExtID": "directory_service",
    # objects
    "objectStoreExtId": "objectstore",
    "certificateExtId": "object_store_certificate",
    # monitoring
    "systemDefinedPolicyExtId": "sda_policy",
    # aiops
    "scenarioExtId": "aiops_scenario",
    # prism
    "nicExtId": "vm_nic",
}


def _resolve_entity_ref(
    field_name: str,
    entity_names: frozenset[str],
) -> str | None:
    """Map a schema field name to the entity it references.

    Args:
        field_name: The schema field name (e.g. ``"role"``,
            ``"fileServerExtId"``, ``"primaryFileServerExtId"``).
        entity_names: Set of all known entity keys from the entity map.

    Returns:
        The matched entity name, or ``None`` if no match is found.
    """
    if field_name in _FIELD_TO_ENTITY_MAP:
        return _FIELD_TO_ENTITY_MAP[field_name]

    if field_name in entity_names:
        return field_name

    stripped = field_name
    for suffix in _REF_SUFFIXES:
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)]
            break

    snake = _camel_to_snake(stripped)
    if snake in entity_names:
        return snake

    for prefix in _REF_PREFIXES:
        if snake.startswith(f"{prefix}_"):
            candidate = snake[len(prefix) + 1 :]
            if candidate in entity_names:
                return candidate

    return None


# ---------------------------------------------------------------------------
# Per-version required helpers
# ---------------------------------------------------------------------------


def _is_required(fmeta: dict[str, Any]) -> bool:
    """Return True if the field is required in any version."""
    return bool(fmeta.get("required_in"))


def _required_label(fmeta: dict[str, Any]) -> str:
    """Build a human-readable required tag for YAML comments.

    Returns:
        ``"REQUIRED"`` when required in all versions, ``"REQUIRED in 4.0"``
        when required in a subset, or ``""`` when never required.
    """
    req_versions = fmeta.get("required_in", [])
    all_versions = fmeta.get("versions", [])
    if not req_versions:
        return ""
    if set(req_versions) == set(all_versions):
        return "REQUIRED"
    return "REQUIRED in " + ", ".join(str(v) for v in req_versions)


def _required_md(fmeta: dict[str, Any]) -> str:
    """Build the Required column value for Markdown tables.

    Returns:
        ``"Yes"``, ``"Yes (4.0 only)"``, or ``"No"``.
    """
    req_versions = fmeta.get("required_in", [])
    all_versions = fmeta.get("versions", [])
    if not req_versions:
        return "No"
    if set(req_versions) == set(all_versions):
        return "Yes"
    ver_str = ", ".join(str(v) for v in req_versions)
    return f"Yes ({ver_str} only)"


# ---------------------------------------------------------------------------
# Example value generation
# ---------------------------------------------------------------------------


def _example_value(
    type_str: str,
    field_name: str,
    schema_example: Any = None,
) -> Any:
    """Generate a smart example value based on type and field name.

    Args:
        type_str: The schema type (e.g. ``"string"``, ``"integer"``).
        field_name: The field name for heuristic fallback values.
        schema_example: Explicit ``example`` value from the OpenAPI spec.
            Used verbatim when present.

    Returns:
        A representative example value.
    """
    if schema_example is not None:
        return schema_example

    lower = field_name.lower()

    if type_str == "boolean":
        if "enabled" in lower or "active" in lower:
            return True
        return "disabled" not in lower

    if type_str == "integer":
        if "port" in lower:
            return 443
        if "memory" in lower or "bytes" in lower:
            return 4294967296
        if "count" in lower or "size" in lower or "sockets" in lower:
            return 2
        return 1

    if type_str == "number":
        return 1.0

    if type_str in ("string", ""):
        if "name" in lower:
            return f"example-{field_name}"
        if "description" in lower:
            return "Example description"
        if "email" in lower:
            return "user@example.com"
        if "ip" in lower or "address" in lower:
            return "192.168.1.1"
        if "uuid" in lower or "id" in lower:
            return "00000000-0000-0000-0000-000000000000"
        if "url" in lower or "uri" in lower:
            return "https://example.com"
        if "password" in lower or "secret" in lower:
            return "<secret>"
        return "example-value"

    return "example-value"


# ---------------------------------------------------------------------------
# Schema -> YAML lines
# ---------------------------------------------------------------------------


def _schema_to_yaml_lines(
    fields: dict[str, Any],
    indent: int = 12,
    depth: int = 0,
    *,
    commented: bool = False,
    entity_names: frozenset[str] | None = None,
    detected_refs: list[str] | None = None,
) -> list[str]:
    """Convert a compat-map schema ``request`` dict to YAML lines.

    Args:
        fields: The ``schema.request`` mapping from the compat map.
        indent: Number of leading spaces for the first level.
        depth: Current recursion depth (caps at ``_MAX_YAML_DEPTH``).
        commented: If True, all lines are prefixed with ``#``.
        entity_names: Known entity keys for cross-entity reference detection.
        detected_refs: Mutable list that accumulates entity types referenced
            via UUID fields.  Caller inspects this after the call to generate
            matching ``data:`` source blocks.

    Returns:
        List of formatted YAML lines (strings).
    """
    lines: list[str] = []
    if depth >= _MAX_YAML_DEPTH:
        return lines

    pad = " " * indent
    prefix = "# " if commented else ""

    for fname, fmeta in fields.items():
        if fname in _SKIP_FIELDS:
            continue
        if fmeta.get("readOnly"):
            continue

        ftype = fmeta.get("type", "string")
        req = _is_required(fmeta)
        req_label = _required_label(fmeta)
        enum_raw = fmeta.get("enum", {})
        versions = fmeta.get("versions", [])
        children = fmeta.get("children") or fmeta.get("properties", {})
        items = fmeta.get("items", {})

        # Build inline comment
        annotations: list[str] = []
        if req_label:
            annotations.append(req_label)

        if ftype == "enum" and enum_raw:
            enum_keys = _filter_enum(
                list(enum_raw.keys())
                if isinstance(enum_raw, dict)
                else [str(v) for v in enum_raw]
            )
            if enum_keys:
                annotations.append(f"enum: {', '.join(enum_keys)}")
        else:
            annotations.append(ftype)

        # version gating
        if versions and isinstance(versions, list):
            ver_strs = [str(v) for v in versions]
            if len(ver_strs) < 3:
                annotations.append(f"v{'+, v'.join(ver_strs)}")

        comment = f"  # {' | '.join(annotations)}" if annotations else ""

        # Determine value
        is_optional = not req
        line_prefix = "# " if (is_optional and not commented) else prefix

        # --- oneOf expansion (flat inline with $objectType) ---
        variants = fmeta.get("variants", {})
        if ftype == "oneOf" and variants:
            variant_names = list(variants.keys())
            oneof_label = " | ".join(variant_names)
            req_tag = f"{req_label} | " if req_label else ""
            lines.append(f"{pad}{line_prefix}{fname}:  # {req_tag}oneOf: {oneof_label}")
            inner_pad = f"{pad}  "
            for idx, (_, vmeta) in enumerate(variants.items()):
                v_props = vmeta.get("properties", {})
                obj_type = vmeta.get("object_type", "")
                is_first = idx == 0
                if is_first:
                    lines.append(f'{inner_pad}{line_prefix}"$objectType": "{obj_type}"')
                    if v_props:
                        child_lines = _schema_to_yaml_lines(
                            v_props,
                            indent=indent + 2,
                            depth=depth + 1,
                            commented=is_optional or commented,
                            entity_names=entity_names,
                            detected_refs=detected_refs,
                        )
                        lines.extend(child_lines)
                else:
                    lines.append(f"{inner_pad}# --- OR ---")
                    lines.append(f'{inner_pad}# "$objectType": "{obj_type}"')
                    if v_props:
                        child_lines = _schema_to_yaml_lines(
                            v_props,
                            indent=indent + 2,
                            depth=depth + 1,
                            commented=True,
                            entity_names=entity_names,
                            detected_refs=detected_refs,
                        )
                        lines.extend(child_lines)
            continue

        if ftype == "enum" and enum_raw:
            enum_keys = _filter_enum(
                list(enum_raw.keys())
                if isinstance(enum_raw, dict)
                else [str(v) for v in enum_raw]
            )
            value = f'"{enum_keys[0]}"' if enum_keys else '"example-value"'
            lines.append(f"{pad}{line_prefix}{fname}: {value}{comment}")

        elif ftype == "object" and children:
            lines.append(f"{pad}{line_prefix}{fname}:{comment}")
            child_lines = _schema_to_yaml_lines(
                children,
                indent=indent + 2,
                depth=depth + 1,
                commented=is_optional or commented,
                entity_names=entity_names,
                detected_refs=detected_refs,
            )
            lines.extend(child_lines)

        elif ftype == "array":
            item_props = items.get("properties", {}) if items else {}
            if item_props:
                lines.append(f"{pad}{line_prefix}{fname}:{comment}")
                item_prefix = "# " if (is_optional and not commented) else prefix
                lines.append(f"{pad}  {item_prefix}- ")
                child_lines = _schema_to_yaml_lines(
                    item_props,
                    indent=indent + 4,
                    depth=depth + 1,
                    commented=is_optional or commented,
                    entity_names=entity_names,
                    detected_refs=detected_refs,
                )
                lines.extend(child_lines)
            elif items and items.get("type"):
                item_ex = items.get("example")
                item_type = items["type"]
                val = _example_value(item_type, fname, item_ex)
                if isinstance(val, str):
                    val = f'"{val}"'
                lines.append(f"{pad}{line_prefix}{fname}:{comment}")
                lines.append(f"{pad}  {line_prefix}- {val}")
            else:
                lines.append(f"{pad}{line_prefix}{fname}: []{comment}")

        else:
            schema_ex = fmeta.get("example")
            value = _example_value(ftype, fname, schema_ex)
            if isinstance(value, str):
                ref_entity = (
                    _resolve_entity_ref(fname, entity_names)
                    if entity_names and _UUID_RE.match(value)
                    else None
                )
                if ref_entity:
                    value = f'"{{data.{ref_entity}.my_{ref_entity}.extId}}"'
                    if detected_refs is not None:
                        detected_refs.append(ref_entity)
                else:
                    value = f'"{value}"'
            elif isinstance(value, bool):
                value = str(value).lower()
            lines.append(f"{pad}{line_prefix}{fname}: {value}{comment}")

    return lines


# ---------------------------------------------------------------------------
# Parameter info for YAML header
# ---------------------------------------------------------------------------


def _is_parent_id_param(
    param: str,
    entity_entry: dict[str, Any],
) -> bool:
    """Return True if *param* is a parent/resource ID rather than a schema field.

    Bare ``extId`` / ``ext_id`` (the entity's own ID) is excluded --
    it is skipped separately by the caller.
    """
    parent_id = entity_entry.get("parent_id_param", "")
    if param == parent_id:
        return True
    lower = param.lower()
    if lower in ("extid", "ext_id"):
        return False
    return lower.endswith("extid")


def _format_parent_params(
    method_params: list[str],
    entity_entry: dict[str, Any],
    *,
    schema_request: dict[str, Any] | None = None,
) -> list[str]:
    """Return YAML lines for non-body, non-odata method parameters.

    For no-body entities (where ``schema_request`` is provided), params
    that match schema fields are rendered with example values from the
    schema instead of dependency ext_id references.

    Args:
        method_params: The ``method_params`` list for the operation.
        entity_entry: The entity's entry from the entity map.
        schema_request: Schema request dict from the compat map.  When
            provided, non-parent-ID params are rendered using schema
            metadata instead of dependency references.

    Returns:
        List of formatted YAML lines.
    """
    lines: list[str] = []
    parent = entity_entry.get("parent_entity", "")

    for param in method_params:
        if param in ("body", "extId") or param.startswith("_"):
            continue

        if schema_request and param in schema_request:
            fmeta = schema_request[param]
            if fmeta.get("readOnly", False):
                continue

        if _is_parent_id_param(param, entity_entry):
            pid_fmeta = schema_request.get(param, {}) if schema_request else {}
            pid_label = _required_label(pid_fmeta) or "REQUIRED"
            if parent:
                lines.append(
                    f"          {param}: "
                    f'"{{{parent}.my_{parent}.ext_id}}"'
                    f"  # {pid_label} parent param"
                )
            else:
                lines.append(f'          {param}: "<value>"  # {pid_label} param')
            continue

        if schema_request and param in schema_request:
            fmeta = schema_request[param]
            ftype = fmeta.get("type", "string")
            enum_raw = fmeta.get("enum", {})
            rl = _required_label(fmeta)
            schema_ex = fmeta.get("example")
            versions = fmeta.get("versions", [])

            annotations: list[str] = []
            if rl:
                annotations.append(rl)
            if ftype == "enum" and enum_raw:
                enum_keys = _filter_enum(
                    list(enum_raw.keys())
                    if isinstance(enum_raw, dict)
                    else [str(v) for v in enum_raw]
                )
                annotations.append(
                    f"enum: {', '.join(enum_keys)}" if enum_keys else ftype
                )
            else:
                annotations.append(ftype)
            if versions and isinstance(versions, list) and len(versions) < 3:
                ver_strs = [str(v) for v in versions]
                annotations.append(f"v{'+, v'.join(ver_strs)}")
            comment = f"  # {' | '.join(annotations)}"

            nested = fmeta.get("children") or fmeta.get("properties", {})
            if ftype == "object" and nested:
                lines.append(f"          {param}:{comment}")
                child_lines = _schema_to_yaml_lines(
                    nested,
                    indent=12,
                    commented=not _is_required(fmeta),
                )
                lines.extend(child_lines)
            elif ftype == "enum" and enum_raw:
                enum_keys_val = _filter_enum(
                    list(enum_raw.keys())
                    if isinstance(enum_raw, dict)
                    else [str(v) for v in enum_raw]
                )
                val = f'"{enum_keys_val[0]}"' if enum_keys_val else '"value"'
                lines.append(f"          {param}: {val}{comment}")
            elif ftype == "boolean":
                val = str(_example_value(ftype, param, schema_ex)).lower()
                lines.append(f"          {param}: {val}{comment}")
            elif ftype in ("integer", "number"):
                val = _example_value(ftype, param, schema_ex)
                lines.append(f"          {param}: {val}{comment}")
            else:
                val = f'"{_example_value(ftype, param, schema_ex)}"'
                lines.append(f"          {param}: {val}{comment}")
            continue

        if parent:
            lines.append(
                f"          {param}: "
                f'"{{{parent}.my_{parent}.ext_id}}"'
                f"  # REQUIRED parent param"
            )
        else:
            lines.append(f'          {param}: "<value>"  # REQUIRED param')
    return lines


# ---------------------------------------------------------------------------
# YAML example file
# ---------------------------------------------------------------------------


def _ref_filter_hint(
    ref_entity: str,
    entity_map: dict[str, Any],
    compat: dict[str, Any],
) -> str:
    """Build a sensible filter placeholder for a data-source reference.

    Inspects the referenced entity's list operation for filterable fields
    and picks ``displayName`` or ``name`` when available.
    """
    ref_entry = entity_map.get(ref_entity, {})
    ref_ns = ref_entry.get("namespace", "")
    ref_list = ref_entry.get("list_method_name", "")
    list_op = _get_op_data(compat, ref_ns, ref_list) if ref_list else None
    if list_op:
        filt_fields = [f["field"] for f in list_op.get("filter_examples", [])]
        for preferred in ("displayName", "name", "username"):
            if preferred in filt_fields:
                return f"{preferred} eq '<{ref_entity}-{preferred}>'"
    return f"name eq '<{ref_entity}-name>'"


def _generate_yaml(
    entity_name: str,
    entity_entry: dict[str, Any],
    compat: dict[str, Any],
    entity_map: dict[str, Any],
) -> str:
    """Generate the full YAML example config for one entity."""
    namespace = entity_entry["namespace"]
    sdk_name = entity_entry["sdk_name"]
    docs_url = f"{_DOCS_BASE}?namespace={namespace}&version=v4"

    create_method = entity_entry.get("create_method_name", "")
    list_method = entity_entry.get("list_method_name", "")
    update_method = entity_entry.get("update_method_name", "")
    operations = entity_entry.get("operations", [])
    method_params = entity_entry.get("method_params", {})
    parent = entity_entry.get("parent_entity", "")

    create_op = _get_op_data(compat, namespace, create_method)
    update_op = _get_op_data(compat, namespace, update_method)
    list_op = _get_op_data(compat, namespace, list_method)

    entity_names = frozenset(entity_map)
    detected_refs: list[str] = []

    # Determine which mutating actions are available
    create_supported = entity_entry.get("create_supported", True)
    update_supported = entity_entry.get("update_supported", True)
    delete_supported = entity_entry.get("delete_supported", True)
    has_create = create_supported and bool(create_method)
    has_update = update_supported and bool(update_method)
    has_delete = delete_supported
    has_ops = bool(operations)
    has_resources = has_create or has_update or has_delete or has_ops

    # --- Pre-compute body lines so cross-entity refs are known early ---
    create_body_lines: list[str] = []
    create_params = method_params.get("create", []) if has_create else []
    create_has_body = "body" in create_params
    create_schema = (
        create_op.get("schema", {}).get("request", {})
        if has_create and create_op
        else {}
    )
    if has_create and create_has_body and create_schema:
        create_body_lines = _schema_to_yaml_lines(
            create_schema,
            indent=12,
            entity_names=entity_names,
            detected_refs=detected_refs,
        )

    update_body_lines: list[str] = []
    update_params: list[str] = []
    update_has_body = False
    update_schema: dict[str, Any] = {}
    if has_update and not has_create:
        update_params = method_params.get("update", [])
        update_has_body = "body" in update_params
        update_schema = (
            update_op.get("schema", {}).get("request", {}) if update_op else {}
        )
        if update_has_body and update_schema:
            update_body_lines = _schema_to_yaml_lines(
                update_schema,
                indent=12,
                entity_names=entity_names,
                detected_refs=detected_refs,
            )

    # Pre-scan operation params for cross-entity refs
    if operations:
        for op_name in operations[:3]:
            op_data = _get_op_data(compat, namespace, op_name)
            if not op_data:
                continue
            for pname, pmeta in op_data.get("parameters", {}).items():
                if pmeta.get("in") == "header":
                    continue
                ptype = pmeta.get("type", "string")
                raw = _example_value(ptype, pname)
                if isinstance(raw, str) and _UUID_RE.match(raw):
                    ref = _resolve_entity_ref(pname, entity_names)
                    if ref:
                        detected_refs.append(ref)

    unique_refs = list(
        dict.fromkeys(r for r in detected_refs if r != parent and r != entity_name)
    )

    # --- Start building output lines ---
    lines: list[str] = []

    # Header
    lines.append("---")
    lines.append(f"# {entity_name} Example Configuration")
    lines.append(f"# SDK: {sdk_name} | Namespace: {namespace}")
    lines.append(f"# Reference: config/examples/{namespace}/{entity_name}.md")
    lines.append(f"# Docs: {docs_url}")
    lines.append("")

    # Domain boilerplate
    lines.append("domains:")
    lines.append("  example_domain:")
    lines.append('    host: "<pc-ip>"')
    lines.append('    username: "<username>"')
    lines.append('    password: "<password>"')
    lines.append("")

    # Data section (parent entity + cross-entity refs)
    data_entities: list[tuple[str, str]] = []
    if parent:
        data_entities.append(
            (
                parent,
                f"name eq '<{parent}-name>'",
            )
        )
    for ref in unique_refs:
        data_entities.append(
            (
                ref,
                _ref_filter_hint(ref, entity_map, compat),
            )
        )

    if data_entities:
        lines.append("    # --- Fetch existing resources via filter ---")
        lines.append("    data:")
        for ref_entity, filter_hint in data_entities:
            lines.append(f"      {ref_entity}:")
            lines.append(f"        my_{ref_entity}:")
            lines.append(f'          filter: "{filter_hint}"')
        lines.append("")

    # Resources section (only if the entity supports any mutating actions)
    if has_resources:
        lines.append("    resources:")
        lines.append(f"      {entity_name}:")
        lines.append("")

    # === CREATE ===
    if has_create:
        lines.append("        # === CREATE ===")
        lines.append(f"        my_{entity_name}:")

        parent_lines = _format_parent_params(
            create_params,
            entity_entry,
            schema_request=create_schema if not create_has_body else None,
        )
        lines.extend(parent_lines)

        if create_has_body:
            if create_schema:
                lines.append("          body:")
                lines.extend(create_body_lines)
            elif create_op:
                lines.append("          body: {}")
            else:
                lines.append("          body:")
                lines.append("            # Schema not available in compatibility map")
        lines.append("")

    # === UPDATE ===
    if has_update:
        if has_create:
            lines.append("        # === UPDATE ===")
            lines.append("        # To update, modify the body above and re-run:")
            lines.append("        #   ztf plan   # shows update plan")
            lines.append("        #   ztf apply  # applies changes")
            lines.append("")
        else:
            lines.append("        # === UPDATE (import-then-update) ===")
            lines.append("        # This resource cannot be created -- it must be")
            lines.append("        # imported first, then updated in place.")
            lines.append(f"        my_{entity_name}:")

            parent_lines = _format_parent_params(
                update_params,
                entity_entry,
                schema_request=(update_schema if not update_has_body else None),
            )
            lines.extend(parent_lines)

            if update_has_body:
                if update_schema:
                    lines.append("          body:")
                    lines.extend(update_body_lines)
                else:
                    lines.append("          body: {}")
            lines.append("")

    # === DELETE ===
    if has_delete and has_resources:
        lines.append("        # === DELETE ===")
        lines.append("        # Remove the resource block from input.yml and run:")
        lines.append("        #   ztf plan   # shows delete plan")
        lines.append("        #   ztf apply  # executes delete")
        lines.append("")

    # === OPERATIONS ===
    if operations:
        lines.append("        # === OPERATIONS ===")
        for op_name in operations[:3]:
            op_data = _get_op_data(compat, namespace, op_name)
            op_params_meta = op_data.get("parameters", {}) if op_data else {}
            lines.append(f"        # my_{entity_name}:")
            lines.append("        #   operations:")
            lines.append(f"        #     - type: {op_name}")
            user_params = {
                k: v for k, v in op_params_meta.items() if v.get("in") != "header"
            }
            if user_params:
                lines.append("        #       params:")
                for pname, pmeta in user_params.items():
                    ptype = pmeta.get("type", "string")
                    penum = pmeta.get("enum", [])
                    if penum:
                        val = _filter_enum(penum)
                        ex = f'"{val[0]}"' if val else '"value"'
                    else:
                        raw = _example_value(ptype, pname)
                        ref = (
                            _resolve_entity_ref(pname, entity_names)
                            if isinstance(raw, str) and _UUID_RE.match(raw)
                            else None
                        )
                        if ref:
                            ex = f'"{{data.{ref}.my_{ref}.extId}}"'
                            detected_refs.append(ref)
                        else:
                            ex = f'"{raw}"'
                    lines.append(f"        #         {pname}: {ex}")
            op_schema = op_data.get("schema", {}).get("request", {}) if op_data else {}
            if op_schema:
                lines.append("        #       body:")
                body_lines = _schema_to_yaml_lines(
                    op_schema,
                    indent=16,
                    commented=True,
                    entity_names=entity_names,
                )
                for bl in body_lines:
                    hash_pos = bl.index("# ")
                    inner_pad = " " * max(hash_pos - 8, 0)
                    lines.append(f"        # {inner_pad}{bl[hash_pos + 2 :]}")
            lines.append("")
        if len(operations) > 3:
            remaining = ", ".join(operations[3:])
            lines.append(f"        # Other operations: {remaining}")
            lines.append("")

    # === DATA SOURCE (list-only via filter) ===
    lines.append("    # --- Fetch by ext_id (data source, list-only) ---")
    lines.append("    # data:")
    lines.append(f"    #   {entity_name}:")
    lines.append(f"    #     existing_{entity_name}:")
    lines.append("    #       filter: \"extId eq '<known-ext-id>'\"")
    lines.append("")

    # List with filter
    if list_method:
        lines.append("    # --- List with filter ---")
        lines.append("    # data:")
        lines.append(f"    #   {entity_name}:")
        lines.append(f"    #     filtered_{entity_name}s:")
        if list_op:
            filt_examples = list_op.get("filter_examples", [])
            if filt_examples:
                first_filt = filt_examples[0]
                raw_example = first_filt.get("example", "")
                filter_expr = _extract_odata_expr(raw_example)
                lines.append(f'    #       filter: "{filter_expr}"')
                filt_fields = [f["field"] for f in filt_examples]
                lines.append(
                    f"    #       # Filterable fields: {', '.join(filt_fields)}"
                )
            else:
                lines.append('    #       filter: "<filter-expression>"')

            order_examples = list_op.get("orderby_examples", [])
            if order_examples:
                order_fields = [f["field"] for f in order_examples]
                lines.append(
                    f"    #       # Orderable fields: {', '.join(order_fields)}"
                )

            select_fields = list_op.get("select_fields", [])
            if select_fields:
                lines.append(
                    f"    #       # Selectable fields: {', '.join(select_fields[:10])}"
                )
                if len(select_fields) > 10:
                    lines.append(
                        f"    #       #   ... and {len(select_fields) - 10} more"
                    )
        else:
            lines.append('    #       filter: "<filter-expression>"')
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Markdown reference file
# ---------------------------------------------------------------------------


def _md_escape(text: str) -> str:
    """Escape pipe chars for Markdown tables."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _generate_markdown(
    entity_name: str,
    entity_entry: dict[str, Any],
    compat: dict[str, Any],
) -> str:
    """Generate a Markdown reference doc for one entity."""
    namespace = entity_entry["namespace"]
    sdk_name = entity_entry["sdk_name"]
    docs_url = f"{_DOCS_BASE}?namespace={namespace}&version=v4"

    create_method = entity_entry.get("create_method_name", "")
    get_method = entity_entry.get("get_method_name", "")
    update_method = entity_entry.get("update_method_name", "")
    delete_method = entity_entry.get("delete_method_name", "")
    list_method = entity_entry.get("list_method_name", "")
    operations = entity_entry.get("operations", [])
    parent = entity_entry.get("parent_entity", "")

    create_op = _get_op_data(compat, namespace, create_method)
    update_op = _get_op_data(compat, namespace, update_method)
    list_op = _get_op_data(compat, namespace, list_method)

    sections: list[str] = []

    # Title
    sections.append(f"# {entity_name}\n")
    sections.append(f"**SDK:** `{sdk_name}` | **Namespace:** `{namespace}`\n")
    sections.append(f"**API Docs:** <{docs_url}>\n")

    # Parent entity
    if parent:
        sections.append("## Parent Entity\n")
        sections.append(f"- Requires: `{parent}`")
        method_params = entity_entry.get("method_params", {})
        create_params = method_params.get("create", [])
        for param in create_params:
            if param not in ("body", "extId") and not param.startswith("_"):
                sections.append(f"- Parent param: `{param}`")
        sections.append("")

    # Operations table
    sections.append("## Operations\n")
    sections.append("| Operation | Method | Supported |")
    sections.append("|-----------|--------|-----------|")

    op_map = {
        "Create": (create_method, entity_entry.get("create_supported", True)),
        "Get": (get_method, True),
        "Update": (update_method, entity_entry.get("update_supported", True)),
        "Delete": (delete_method, entity_entry.get("delete_supported", True)),
        "List": (list_method, True),
    }
    for op_label, (method, supported) in op_map.items():
        if method:
            supported_str = "Yes" if supported else "No"
            sections.append(f"| {op_label} | `{method}` | {supported_str} |")
        elif not supported:
            sections.append(f"| {op_label} | - | No |")
    sections.append("")

    if operations:
        sections.append("### Custom Operations\n")
        for op_name in operations:
            op_data = _get_op_data(compat, namespace, op_name)
            summary = ""
            if op_data:
                summary = op_data.get("summary", "")
            if summary:
                sections.append(f"- `{op_name}` -- {summary}")
            else:
                sections.append(f"- `{op_name}`")
        sections.append("")

        for op_name in operations:
            op_data = _get_op_data(compat, namespace, op_name)
            if not op_data:
                continue
            op_schema = op_data.get("schema", {}).get("request", {})
            if not op_schema:
                continue
            sections.append(f"#### `{op_name}` Schema\n")
            sections.append(
                "| Field | Type | Required | Description "
                "| Versions | Enum Values | Constraints |"
            )
            sections.append(
                "|-------|------|----------|-------------|"
                "----------|-------------|-------------|"
            )
            _md_schema_rows(op_schema, sections, depth=0)
            sections.append("")

    # Create / Update schema table
    _schema_table_rendered = False
    if create_op:
        schema_request = create_op.get("schema", {}).get("request", {})
        if schema_request:
            sections.append("## Create Schema\n")
            sections.append(
                "| Field | Type | Required | Description "
                "| Versions | Enum Values | Constraints |"
            )
            sections.append(
                "|-------|------|----------|-------------|"
                "----------|-------------|-------------|"
            )
            _md_schema_rows(schema_request, sections, depth=0)
            sections.append("")
            _schema_table_rendered = True

    if not _schema_table_rendered and update_op:
        schema_request = update_op.get("schema", {}).get("request", {})
        if schema_request:
            sections.append("## Update Schema\n")
            sections.append(
                "| Field | Type | Required | Description "
                "| Versions | Enum Values | Constraints |"
            )
            sections.append(
                "|-------|------|----------|-------------|"
                "----------|-------------|-------------|"
            )
            _md_schema_rows(schema_request, sections, depth=0)
            sections.append("")

    # Parameters (from create operation)
    if create_op:
        params = {
            k: v
            for k, v in create_op.get("parameters", {}).items()
            if v.get("in") != "header"
        }
        if params:
            sections.append("## Operation Parameters (Create)\n")
            sections.append(
                "| Parameter | Type | Required | In | Description | Enum Values |"
            )
            sections.append(
                "|-----------|------|----------|----|-------------|-------------|"
            )
            for pname, pmeta in params.items():
                ptype = pmeta.get("type", "string")
                preq = "Yes" if pmeta.get("required") else "No"
                pin = pmeta.get("in", "query")
                pdesc = _md_escape(pmeta.get("description", ""))[:80]
                penum = _filter_enum(pmeta.get("enum", []))
                penum_str = ", ".join(penum) if penum else "-"
                sections.append(
                    f"| `{pname}` | {ptype} | {preq} | {pin} | {pdesc} | {penum_str} |"
                )
            sections.append("")

    # Filter / Sort / Select
    if list_op:
        filt = list_op.get("filter_examples", [])
        order = list_op.get("orderby_examples", [])
        select = list_op.get("select_fields", [])

        if filt or order or select:
            sections.append("## Filter / Sort / Select (List)\n")

        if filt:
            sections.append("### Filters\n")
            sections.append("| Field | Example |")
            sections.append("|-------|---------|")
            for f in filt:
                raw = f.get("example", "")
                expr = _extract_odata_expr(raw)
                sections.append(f"| {f['field']} | `{expr}` |")
            sections.append("")

        if order:
            sections.append("### Orderby\n")
            sections.append("| Field | Example |")
            sections.append("|-------|---------|")
            for o in order:
                raw = o.get("example", "")
                expr = _extract_odata_expr(raw)
                sections.append(f"| {o['field']} | `{expr}` |")
            sections.append("")

        if select:
            sections.append("### Select Fields\n")
            sections.append(", ".join(f"`{s}`" for s in select))
            sections.append("")

    return "\n".join(sections) + "\n"


def _format_constraints(fmeta: dict[str, Any]) -> str:
    """Build a compact constraints string from schema metadata."""
    parts: list[str] = []
    pattern = fmeta.get("pattern")
    if pattern:
        parts.append(f"pattern: `{pattern}`")
    min_len = fmeta.get("minLength")
    max_len = fmeta.get("maxLength")
    if min_len is not None and max_len is not None:
        parts.append(f"len: {min_len}..{max_len}")
    elif min_len is not None:
        parts.append(f"minLen: {min_len}")
    elif max_len is not None:
        parts.append(f"maxLen: {max_len}")
    min_items = fmeta.get("minItems")
    max_items = fmeta.get("maxItems")
    if min_items is not None and max_items is not None:
        parts.append(f"items: {min_items}..{max_items}")
    elif min_items is not None:
        parts.append(f"minItems: {min_items}")
    elif max_items is not None:
        parts.append(f"maxItems: {max_items}")
    return "; ".join(parts) if parts else "-"


def _md_schema_rows(
    fields: dict[str, Any],
    sections: list[str],
    depth: int,
    prefix: str = "",
) -> None:
    """Recursively append Markdown table rows for schema fields."""
    for fname, fmeta in fields.items():
        if fname in _SKIP_FIELDS:
            continue
        if fmeta.get("readOnly"):
            continue

        display_name = f"{'&nbsp;&nbsp;' * depth}{prefix}{fname}"
        ftype = fmeta.get("type", "string")
        required = _required_md(fmeta)
        desc = _md_escape(fmeta.get("description", ""))[:120]
        versions = fmeta.get("versions", [])
        ver_str = ", ".join(str(v) for v in versions) if versions else "-"
        constraints = _format_constraints(fmeta)

        enum_raw = fmeta.get("enum", {})
        if enum_raw:
            enum_keys = _filter_enum(
                list(enum_raw.keys())
                if isinstance(enum_raw, dict)
                else [str(v) for v in enum_raw]
            )
            enum_str = ", ".join(enum_keys) if enum_keys else "-"
        else:
            enum_str = "-"

        # --- oneOf expansion ---
        variants = fmeta.get("variants", {})
        if ftype == "oneOf" and variants:
            variant_names = list(variants.keys())
            mutual_note = f"Mutually exclusive: {', '.join(variant_names)}"
            sections.append(
                f"| {display_name} | oneOf | {required} "
                f"| {mutual_note} | {ver_str} | - | - |"
            )
            indent = "&nbsp;&nbsp;" * (depth + 1)
            sections.append(
                f"| {indent}$objectType | string | Yes "
                f"| Discriminator -- set to the variant's "
                f"object_type value | - | - | - |"
            )
            for vname, vmeta in variants.items():
                v_props = vmeta.get("properties", {})
                obj_type = vmeta.get("object_type", "")
                sections.append(
                    f'| {indent}**{vname}** (`$objectType: "{obj_type}"`) | | | | | | |'
                )
                if v_props:
                    _md_schema_rows(
                        v_props,
                        sections,
                        depth + 2,
                    )
            continue

        sections.append(
            f"| {display_name} | {ftype} | {required} "
            f"| {desc} | {ver_str} | {enum_str} | {constraints} |"
        )

        # Recurse into children / items
        children = fmeta.get("children") or fmeta.get("properties", {})
        if children:
            _md_schema_rows(children, sections, depth + 1)

        items = fmeta.get("items", {})
        if items:
            item_props = items.get("properties", {})
            if item_props:
                _md_schema_rows(item_props, sections, depth + 1, "[].")
            elif items.get("type"):
                item_indent = "&nbsp;&nbsp;" * (depth + 1)
                item_constraints = _format_constraints(items)
                sections.append(
                    f"| {item_indent}[].item | {items['type']} | - "
                    f"| - | - | - | {item_constraints} |"
                )


# ---------------------------------------------------------------------------
# Starter functions.py
# ---------------------------------------------------------------------------

_FUNCTIONS_PY_CONTENT = '''\
"""User-defined functions for ZTF interpolation.

Place this file alongside your input.yml or specify its path with
``--functions config/functions.py``.  Every public function defined here
becomes available in YAML via the ``{fn.<name>(<args>)}`` token syntax.

Example usage in input.yml::

    body:
      name: "vm-{fn.pad(each.value, 4)}"
      guestCustomization:
        config:
          cloudInit:
            userData: "{fn.b64encode(fn.template(cloud-init.tpl))}"

Third-party imports:
    Stdlib modules (csv, json, base64, etc.) are always available.
    Third-party packages must be installed in the ZTF environment:
        uv pip install <package>
"""

import base64
from pathlib import Path


def pad(value: object, width: int = 4) -> str:
    """Zero-pad a numeric value to *width* digits.

    Replaces Terraform's ``format("%0Nd", n)``.

    Args:
        value: Number or numeric string to pad.
        width: Total width of the resulting string.

    Returns:
        Zero-padded string, e.g. ``pad(1, 4)`` -> ``"0001"``.
    """
    return str(int(value)).zfill(int(width))


def b64encode(value: str) -> str:
    """Base64-encode a UTF-8 string.

    Replaces Terraform's ``base64encode()``.

    Args:
        value: Plain-text string to encode.

    Returns:
        Base64-encoded string.
    """
    return base64.b64encode(value.encode()).decode()


def b64decode(value: str) -> str:
    """Base64-decode a string back to UTF-8.

    Replaces Terraform's ``base64decode()``.

    Args:
        value: Base64-encoded string.

    Returns:
        Decoded plain-text string.
    """
    return base64.b64decode(value.encode()).decode()


def template(path: str) -> str:
    """Read a template file and resolve ``{token}`` placeholders.

    The template file uses the **same** interpolation syntax as
    ``input.yml`` (``{var.*}``, ``{each.*}``, ``{data.*}``,
    ``{fn.*}``).  The current interpolation context is passed
    through automatically -- no explicit variable arguments needed.

    Replaces Terraform's ``templatefile(path, vars)``.

    Note:
        ``fn.template()`` is a built-in that the ZTF engine handles
        specially.  This function is included here for documentation
        and as a fallback for standalone testing.

    Args:
        path: Path to the template file (relative to the config
            directory or absolute).

    Returns:
        Rendered template string with all tokens resolved.
    """
    return Path(path).read_text()


def read_file(path: str) -> str:
    """Read the entire contents of a file as a string.

    Replaces Terraform's ``file(path)``.

    Args:
        path: Path to the file.

    Returns:
        File contents as a string.
    """
    return Path(path).read_text()


def read_lines(path: str) -> list[str]:
    """Read a file and return non-empty lines as a list.

    Useful for IP lists, host lists, or simple CSV files with one
    value per line.  Replaces Terraform's ``csvdecode(file(path))``
    for single-column data.

    Args:
        path: Path to the file.

    Returns:
        List of stripped, non-empty lines.
    """
    return [
        line.strip()
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Convenience functions (not required for TF parity, but useful)
# ---------------------------------------------------------------------------


def upper(value: str) -> str:
    """Convert string to uppercase."""
    return str(value).upper()


def lower(value: str) -> str:
    """Convert string to lowercase."""
    return str(value).lower()


def join(separator: str, *values: object) -> str:
    """Join values with a separator string."""
    return separator.join(str(v) for v in values)
'''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_all(
    namespace_filter: str | None = None,
    output_dir: Path | None = None,
) -> None:
    """Generate example configs and reference docs for entities.

    Args:
        namespace_filter: If provided, only generate for this namespace.
            If ``None``, generate for all namespaces.
        output_dir: Directory to write examples into.
            Defaults to ``./examples/`` in the current working directory.
    """
    out = output_dir if output_dir is not None else _OUTPUT_DIR
    entity_map = _load_entity_map()
    compat = _load_compat_map()

    # Group by namespace
    by_namespace: dict[str, dict[str, dict[str, Any]]] = {}
    for ename, edata in entity_map.items():
        ns = edata.get("namespace", "unknown")
        by_namespace.setdefault(ns, {})[ename] = edata

    if namespace_filter:
        if namespace_filter not in by_namespace:
            available = ", ".join(sorted(by_namespace))
            logger.error(
                f"Namespace {namespace_filter!r} not found. Available: {available}"
            )
            return
        by_namespace = {namespace_filter: by_namespace[namespace_filter]}

    total = sum(len(entities) for entities in by_namespace.values())
    generated = 0

    for ns in sorted(by_namespace):
        ns_dir = out / ns
        ns_dir.mkdir(parents=True, exist_ok=True)

        for ename in sorted(by_namespace[ns]):
            edata = by_namespace[ns][ename]

            # YAML example
            yaml_content = _generate_yaml(ename, edata, compat, entity_map)
            yaml_path = ns_dir / f"{ename}.yml"
            yaml_path.write_text(yaml_content, encoding="utf-8")

            # Markdown reference
            md_content = _generate_markdown(ename, edata, compat)
            md_path = ns_dir / f"{ename}.md"
            md_path.write_text(md_content, encoding="utf-8")

            generated += 1

    print(f"\nGenerated {generated}/{total} entity examples in {out}")

    # Write starter functions.py (skip when filtering by namespace)
    if not namespace_filter:
        fn_path = out / "functions.py"
        fn_path.write_text(_FUNCTIONS_PY_CONTENT, encoding="utf-8")
        print(f"Wrote starter functions file: {fn_path}")

    # Build INDEX.md from the full entity_map (not the filtered subset)
    # so that --namespace runs don't clobber entries for other namespaces.
    all_by_namespace: dict[str, list[str]] = {}
    for ename, edata in entity_map.items():
        ns = edata.get("namespace", "unknown")
        all_by_namespace.setdefault(ns, []).append(ename)

    index_lines = ["# Entity Example Configs\n"]
    index_lines.append(
        "Auto-generated example configurations and reference docs "
        "for all ZTF entities.\n"
    )
    index_lines.append("## Custom Functions\n")
    index_lines.append(
        "A starter [functions.py](functions.py) is included with common "
        "helper functions (`pad`, `b64encode`, `template`, `read_file`, "
        "etc.). Copy it alongside your `input.yml` and customise as needed. "
        "See the [Advanced Topics](../docs/advanced-topics.md) guide for "
        "full documentation.\n"
    )

    for ns in sorted(all_by_namespace):
        entities = sorted(all_by_namespace[ns])
        index_lines.append(f"## {ns} ({len(entities)} entities)\n")
        index_lines.append("| Entity | YAML Example | Reference |")
        index_lines.append("|--------|-------------|-----------|")
        for ename in entities:
            index_lines.append(
                f"| {ename} "
                f"| [{ename}.yml]({ns}/{ename}.yml) "
                f"| [{ename}.md]({ns}/{ename}.md) |"
            )
        index_lines.append("")

    index_path = out / "INDEX.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"Wrote index: {index_path}")
