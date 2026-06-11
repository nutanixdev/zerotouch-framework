"""Config loader for the domain-grouped YAML format.

Responsibilities:

1. Parse and validate the YAML config structure.
2. Merge ``--var`` / ``--var-file`` overrides into ``variables:``.
3. Resolve ``{var.*}`` tokens in all values.
4. Expand ``for_each`` and ``count`` templates into concrete resources.
5. Merge per-resource ``rules`` with global ``defaults.rules``.
6. Validate resource-name uniqueness within each domain.
"""

from copy import deepcopy
from typing import Any

import yaml

from ztf.config.interpolation import InterpolationContext, resolve
from ztf.utils.utils import get_logger

logger = get_logger(__name__)

DEFAULT_RULES: dict[str, Any] = {
    "prevent_destroy": False,
    "ignore_changes": [],
    "create_before_destroy": False,
}


def _merge_rules(
    base: dict[str, Any], overrides: dict[str, Any] | None
) -> dict[str, Any]:
    """Merge two rule dicts and produce a fresh ``ignore_changes`` list.

    The naive ``{**base, **overrides}`` pattern shallow-copies the dict
    but leaves list values (here, ``ignore_changes``) aliased to the
    same underlying object.  Any in-place mutation (``append``,
    ``extend``) downstream would therefore leak across every resource
    that inherits the default, and -- because ``DEFAULT_RULES`` is at
    module scope -- would even poison subsequent ``load_config`` calls
    in the same process.  Materialising a new list on every merge keeps
    each resource's rule mutations local.
    """
    merged: dict[str, Any] = {**base, **(overrides or {})}
    merged["ignore_changes"] = list(merged.get("ignore_changes") or [])
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    raw_config: dict[str, Any],
    var_overrides: dict[str, Any] | None = None,
    var_files: list[str] | None = None,
    functions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse, validate, and normalise a YAML config into the canonical shape.

    Args:
        raw_config: Raw parsed YAML (from ``yaml.safe_load``).
        var_overrides: Key/value pairs from ``--var`` CLI flags.
        var_files: Paths to YAML files with extra variables.
        functions: User-defined Python functions for ``{fn.*}`` tokens.

    Returns:
        Normalised config dict::

            {
                "variables": {...},
                "defaults": {"rules": {...}},
                "functions": {...},
                "domains": {
                    "<name>": {
                        "host": "...",
                        "username": "...",
                        "password": "...",
                        "data": {...},
                        "resources": {
                            "<entity>": {
                                "<resource_name>": {
                                    "rules": {...},
                                    "body": {...},
                                    "params": {...},
                                    "operations": [...],
                                }
                            }
                        }
                    }
                },
                "outputs": {...},
            }

    Raises:
        ValueError: On invalid structure or duplicate resource names.
    """
    config = deepcopy(raw_config)

    # --- 1. Variables -------------------------------------------------------
    variables: dict[str, Any] = config.get("variables", {})
    if var_files:
        for vf in var_files:
            with open(vf, encoding="utf-8") as fh:
                file_vars = yaml.safe_load(fh) or {}
            if not isinstance(file_vars, dict):
                raise ValueError(
                    f"Variable file '{vf}' must contain a YAML mapping, "
                    f"got {type(file_vars).__name__}"
                )
            variables.update(file_vars)
    if var_overrides:
        variables.update(var_overrides)

    # --- 2. Defaults --------------------------------------------------------
    defaults = config.get("defaults", {})
    default_rules: dict[str, Any] = _merge_rules(DEFAULT_RULES, defaults.get("rules"))

    fn_map = functions or {}

    # Variable-only context (no resource state yet)
    var_ctx = InterpolationContext(variables=variables, functions=fn_map)

    # --- 3. Process each domain ---------------------------------------------
    domains: dict[str, Any] = config.get("domains", {})
    if not domains:
        raise ValueError(
            "Config must include a 'domains' section with at least one domain. If"
            " you want to clear all resources in a domain, keep the file structure"
            " and set 'resources: {}' or delete the resources section under the domain."
        )

    for domain_name, domain_cfg in domains.items():
        # Validate required connection fields
        if not domain_cfg.get("username") or not domain_cfg.get("password"):
            raise ValueError(
                f"Domain '{domain_name}' must include 'username' and 'password'."
            )

        # Resolve variables in connection settings
        for key in ("host", "username", "password"):
            if key in domain_cfg:
                domain_cfg[key] = resolve(domain_cfg[key], var_ctx)

        # Resolve variables in data-source definitions
        data_section: dict[str, dict[str, Any]] = domain_cfg.get("data", {})
        for entity_type in data_section:
            for source_name in data_section[entity_type]:
                data_section[entity_type][source_name] = resolve(
                    data_section[entity_type][source_name], var_ctx
                )

        # Process resources: expand for_each, resolve variables, merge rules
        resources: dict[str, dict[str, Any]] = domain_cfg.get("resources", {})
        expanded_resources: dict[str, dict[str, Any]] = {}

        for entity_type, entity_resources in resources.items():
            expanded_entity: dict[str, Any] = {}

            if not entity_resources:
                raise ValueError(
                    f"Domain '{domain_name}' must include at least one resource under"
                    f" '{entity_type}' or remove the '{entity_type}' section."
                )

            for resource_name, resource_cfg in entity_resources.items():
                if not resource_cfg:
                    raise ValueError(
                        f"Domain '{domain_name}' must include at least one resource"
                        f" under '{entity_type}' with body or params."
                    )

                if "for_each" in resource_cfg or "count" in resource_cfg:
                    # --- count / for_each expansion -------------------------
                    # ``count`` is sugar over ``for_each``: ``count: N``
                    # desugars to ``for_each: {"0": 0, ..., "N-1": N-1}``
                    # so every iteration carries an integer ordinal in
                    # ``each.value`` and the index also appears as
                    # ``each.index`` for parity with Terraform.
                    for_each_map, count_mode = _resolve_iteration_map(
                        resource_cfg, domain_name, entity_type, resource_name
                    )
                    excluded_keys = {"for_each", "count"}
                    template = {
                        k: v for k, v in resource_cfg.items() if k not in excluded_keys
                    }
                    for each_index, (each_key, each_value) in enumerate(
                        for_each_map.items()
                    ):
                        each_ctx = InterpolationContext(
                            variables=variables,
                            for_each={
                                "key": each_key,
                                "value": each_value,
                                "index": each_index,
                            },
                            functions=fn_map,
                        )
                        expanded_name = resolve(resource_name, each_ctx)
                        if expanded_name in expanded_entity:
                            iter_keyword = "count" if count_mode else "for_each"
                            hint = "{each.index}" if count_mode else "{each.key}"
                            raise ValueError(
                                f"Domain '{domain_name}' has a "
                                f"'{iter_keyword}' expansion under "
                                f"'{entity_type}' that produced a duplicate "
                                f"resource name '{expanded_name}'. Adjust the "
                                f"key template '{resource_name}' (e.g. include "
                                f"'{hint}') so every iteration produces a "
                                "unique name."
                            )
                        expanded_cfg = resolve(deepcopy(template), each_ctx)
                        expanded_cfg["rules"] = _merge_rules(
                            default_rules, expanded_cfg.get("rules")
                        )
                        expanded_entity[expanded_name] = expanded_cfg
                else:
                    # --- regular resource -----------------------------------
                    resource_cfg = resolve(resource_cfg, var_ctx)
                    resource_cfg["rules"] = _merge_rules(
                        default_rules, resource_cfg.get("rules")
                    )
                    expanded_entity[resource_name] = resource_cfg

            expanded_resources[entity_type] = expanded_entity

        domain_cfg["resources"] = expanded_resources

        # Validate uniqueness
        _validate_resource_names(domain_name, expanded_resources)

    # --- 4. Outputs (kept verbatim, resolved after apply) -------------------
    outputs: dict[str, Any] = config.get("outputs", {})

    return {
        "variables": variables,
        "defaults": {"rules": default_rules},
        "functions": fn_map,
        "domains": domains,
        "outputs": outputs,
    }


# ---------------------------------------------------------------------------
# Iteration helpers
# ---------------------------------------------------------------------------


def _resolve_iteration_map(
    resource_cfg: dict[str, Any],
    domain_name: str,
    entity_type: str,
    resource_name: str,
) -> tuple[dict[str, Any], bool]:
    """Resolve a resource's iteration directive into a uniform mapping.

    Accepts either:

    * ``for_each: <map>`` -- the map is returned as-is (existing behavior).
    * ``count: <non-negative int>`` -- desugared to
      ``{"0": 0, "1": 1, ..., str(N-1): N-1}`` so the standard for_each
      pipeline can drive count-style expansion without a parallel code
      path.  ``each.value`` carries the integer ordinal; ``each.index``
      (set by the caller) duplicates it for Terraform parity.

    Args:
        resource_cfg: The unexpanded resource configuration.
        domain_name: Owning domain (for error messages).
        entity_type: Owning entity type (for error messages).
        resource_name: Resource name template (for error messages).

    Returns:
        ``(iteration_map, count_mode)``. ``count_mode`` is ``True`` when
        the directive was ``count``, used by the caller to phrase
        duplicate-name errors with the matching keyword.

    Raises:
        ValueError: If both ``count`` and ``for_each`` are set, if
            ``count`` is not a non-negative integer, or if ``for_each``
            is not a mapping.
    """
    has_count = "count" in resource_cfg
    has_for_each = "for_each" in resource_cfg

    if has_count and has_for_each:
        raise ValueError(
            f"Domain '{domain_name}' resource "
            f"'{entity_type}/{resource_name}' sets both 'count' and "
            "'for_each'; they are mutually exclusive."
        )

    if has_count:
        raw_count = resource_cfg["count"]
        # Reject ``True``/``False`` even though they're ``int`` in Python;
        # boolean ``count`` is almost certainly a config bug.
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            raise ValueError(
                f"Domain '{domain_name}' resource "
                f"'{entity_type}/{resource_name}' has 'count' value "
                f"{raw_count!r}; expected a non-negative integer."
            )
        if raw_count < 0:
            raise ValueError(
                f"Domain '{domain_name}' resource "
                f"'{entity_type}/{resource_name}' has 'count' value "
                f"{raw_count}; expected a non-negative integer."
            )
        return {str(i): i for i in range(raw_count)}, True

    for_each = resource_cfg["for_each"]
    # A non-mapping ``for_each`` would otherwise surface as a cryptic
    # ``AttributeError: '<type>' object has no attribute 'items'`` deep
    # in the expansion loop; fail fast with a user-facing message.
    if not isinstance(for_each, dict):
        raise ValueError(
            f"Domain '{domain_name}' resource "
            f"'{entity_type}/{resource_name}' has 'for_each' of type "
            f"{type(for_each).__name__}; expected a mapping (YAML dict)."
        )
    return for_each, False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_resource_names(
    domain_name: str, resources: dict[str, dict[str, Any]]
) -> None:
    """Ensure resource names are unique within a domain across entity types.

    Raises:
        ValueError: If a duplicate name is found.
    """
    seen: set[str] = set()
    for _, entity_resources in resources.items():
        for resource_name in entity_resources:
            if resource_name in seen:
                raise ValueError(
                    f"Duplicate resource name '{resource_name}' in domain "
                    f"'{domain_name}'. Resource names must be unique within a "
                    f"domain across all entity types."
                )
            seen.add(resource_name)


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def parse_var_string(var_str: str) -> tuple[str, str]:
    """Parse a ``--var 'key=value'`` CLI argument.

    Returns:
        ``(key, value)`` tuple.

    Raises:
        ValueError: If the string doesn't contain ``=``.
    """
    if "=" not in var_str:
        raise ValueError(f"Invalid --var format: '{var_str}'. Expected 'key=value'.")
    key, _, value = var_str.partition("=")
    return key.strip(), value.strip()
