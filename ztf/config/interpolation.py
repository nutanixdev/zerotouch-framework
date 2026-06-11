"""Interpolation engine for ``{scope.path}`` token resolution.

Supported token patterns:

+---------------------------------+------------------------------------------+
| Pattern                         | Resolves to                              |
+---------------------------------+------------------------------------------+
| ``{var.name}``                  | Variable value                           |
| ``{each.key}``                  | Current for_each key                     |
| ``{each.value}``                | Current for_each value                   |
| ``{each.value.field}``          | Field from for_each value                |
| ``{each.index}``                | 0-based ordinal of the current iteration |
| ``{data.entity.name.field}``    | Field from data source                   |
| ``{fn.name(args)}``             | User-defined Python function call        |
| ``{resource_name.ext_id}``      | ext_id of resource (same domain)         |
| ``{resource_name.body.field}``  | Body field of resource (same domain)     |
| ``{domain.resource_name.field}``| Cross-domain resource reference          |
+---------------------------------+------------------------------------------+
"""

import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ztf.utils.utils import get_logger

logger = get_logger(__name__)

_TOKEN_PATTERN = re.compile(r"\{((?:[^{}]|\{[^{}]*\})+)\}")

#: Upper bound on nested interpolation token resolution depth.  Prevents
#: stack exhaustion from pathological configs like
#: ``{fn.a({fn.b({fn.c(...)})})}`` or circular tokens that keep expanding.
_MAX_TOKEN_DEPTH: int = 32

#: Directory that ``{fn.template(...)}`` is permitted to read from.
#: Populated at import time (cwd) and resettable for tests.
_TEMPLATE_ROOT: Path = Path.cwd().resolve()


def set_template_root(root: str | Path) -> None:
    """Override the sandbox directory for ``{fn.template(...)}``.

    Primarily useful for tests; in production the default (``Path.cwd()``
    at import time) is correct for the standard ``ztf apply`` workflow
    where users keep templates alongside ``config/input.yml``.
    """
    global _TEMPLATE_ROOT
    _TEMPLATE_ROOT = Path(root).resolve()


class InterpolationContext:
    """Holds all scopes needed to resolve interpolation tokens.

    Args:
        variables: Static variables from the ``variables:`` section.
        for_each: Current for_each iteration (``{"key": ..., "value": ...}``).
        resource_state: Resources in the current domain that have been applied.
            ``{resource_name: {"ext_id": ..., "body": {...}, ...}}``.
        data_cache: Cached data-source query results.
            ``{entity_type: {source_name: {"data": [...], "metadata": {...}}}}``
            or domain-scoped:
            ``{domain: {entity_type: {source_name: {"data": [...], "metadata": {...}}}}}``.
        domain_states: Resource state from *other* domains (for cross-domain refs).
            ``{domain_name: {resource_name: {"ext_id": ..., ...}}}``.
        current_domain: Name of the domain currently being processed.
        functions: User-defined Python functions available as ``{fn.*}``
            tokens.  ``{name: callable}``.
    """

    __slots__ = (
        "variables",
        "for_each",
        "resource_state",
        "data_cache",
        "domain_states",
        "current_domain",
        "functions",
    )

    def __init__(
        self,
        variables: dict[str, Any] | None = None,
        for_each: dict[str, Any] | None = None,
        resource_state: dict[str, dict[str, Any]] | None = None,
        data_cache: dict[str, dict[str, dict[str, Any]]] | None = None,
        domain_states: dict[str, dict[str, dict[str, Any]]] | None = None,
        current_domain: str | None = None,
        functions: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.variables = variables or {}
        self.for_each = for_each
        self.resource_state = resource_state or {}
        self.data_cache = data_cache or {}
        self.domain_states = domain_states or {}
        self.current_domain = current_domain
        self.functions = functions or {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_UNRESOLVED = object()  # sentinel for "token could not be resolved"


def _walk_path(obj: Any, parts: list[str]) -> Any:
    """Drill into a nested dict following *parts* as keys.

    Returns ``_UNRESOLVED`` if any key is missing.
    """
    value = obj
    for part in parts:
        if isinstance(value, dict):
            if part in value:
                value = value[part]
                continue
            if part == "ext_id" and "extId" in value:
                value = value["extId"]
                continue
            if part == "extId" and "ext_id" in value:
                value = value["ext_id"]
                continue
            return _UNRESOLVED
        if isinstance(value, list):
            if part.isdigit():
                index = int(part)
                if 0 <= index < len(value):
                    value = value[index]
                    continue
                return _UNRESOLVED
            return _UNRESOLVED
        return _UNRESOLVED
    return value


# ---------------------------------------------------------------------------
# Function token helpers
# ---------------------------------------------------------------------------

_FN_CALL_PATTERN = re.compile(r"^fn\.(\w+)\((.*)?\)$", re.DOTALL)


def _split_fn_args(args_str: str) -> list[str]:
    """Split comma-separated function arguments respecting nested parens.

    ``"fn.pad(each.value, 4)"`` has args ``["each.value", "4"]``.
    ``"fn.b64encode(fn.template(cloud-init.tpl))"`` has args
    ``["fn.template(cloud-init.tpl)"]`` (inner parens preserved).
    """
    if not args_str or not args_str.strip():
        return []
    args: list[str] = []
    current: list[str] = []
    depth = 0
    for char in args_str:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                logger.warning("Mismatched parentheses in fn args: %s", args_str)
                return [args_str.strip()]
        elif char == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if depth != 0:
        logger.warning("Unclosed parentheses in fn args: %s", args_str)
        return [args_str.strip()]
    if current:
        tail = "".join(current).strip()
        if tail:
            args.append(tail)
    return args


def _resolve_fn_arg(raw_arg: str, ctx: "InterpolationContext", _depth: int = 0) -> Any:
    """Resolve a single function argument.

    An argument can be:
    - A nested ``fn.*()`` call  -> resolved recursively
    - A scoped token like ``var.name`` or ``each.value.field`` -> resolved
    - A bare literal string or number -> returned as-is
    """
    # Nested fn call
    if _FN_CALL_PATTERN.match(raw_arg):
        result = _resolve_fn_call(raw_arg, ctx, _depth=_depth + 1)
        if result is _UNRESOLVED:
            return _UNRESOLVED
        return result

    # Scoped token (var.x, each.value.x, data.x.y.z, resource.field)
    if "." in raw_arg:
        result = _resolve_token_inner(raw_arg, ctx)
        if result is not _UNRESOLVED:
            return result

    # Numeric literal
    if raw_arg.isdigit():
        return int(raw_arg)

    # Bare string literal (e.g. a file path like "cloud-init.tpl")
    return raw_arg


def _resolve_fn_call(token: str, ctx: "InterpolationContext", _depth: int = 0) -> Any:
    """Resolve a ``fn.name(arg1, arg2, ...)`` token.

    Returns ``_UNRESOLVED`` if the function is not registered, any
    required argument cannot be resolved, or the nested-resolution
    depth exceeds ``_MAX_TOKEN_DEPTH``.
    """
    if _depth >= _MAX_TOKEN_DEPTH:
        logger.error(
            "Interpolation recursion depth exceeded (%d) in fn call: %s",
            _MAX_TOKEN_DEPTH,
            token,
        )
        return _UNRESOLVED

    match = _FN_CALL_PATTERN.match(token)
    if not match:
        return _UNRESOLVED

    fn_name = match.group(1)
    raw_args_str = match.group(2) or ""

    raw_args = _split_fn_args(raw_args_str)
    resolved_args: list[Any] = []
    for raw_arg in raw_args:
        resolved = _resolve_fn_arg(raw_arg, ctx, _depth=_depth + 1)
        if resolved is _UNRESOLVED:
            return _UNRESOLVED
        resolved_args.append(resolved)

    # Built-in: resolve {tokens} in a template file
    if fn_name == "template" and resolved_args:
        raw_path = str(resolved_args[0])
        try:
            candidate = (_TEMPLATE_ROOT / raw_path).resolve()
        except (OSError, RuntimeError):
            logger.warning("Template path could not be resolved: %s", raw_path)
            return _UNRESOLVED
        # Sandbox: reject anything that escapes the template root (e.g.
        # ``../../etc/passwd`` or an absolute path pointing outside
        # the project tree).
        try:
            candidate.relative_to(_TEMPLATE_ROOT)
        except ValueError:
            logger.error(
                "Refusing to load template '%s': resolves to '%s' which is "
                "outside the allowed root '%s'.",
                raw_path,
                candidate,
                _TEMPLATE_ROOT,
            )
            return _UNRESOLVED
        if not candidate.is_file():
            logger.warning("Template file not found: %s", candidate)
            return _UNRESOLVED
        raw_content = candidate.read_text(encoding="utf-8")
        return resolve(raw_content, ctx, _depth=_depth + 1)

    func = ctx.functions.get(fn_name)
    if func is None:
        return _UNRESOLVED

    try:
        return func(*resolved_args)
    except Exception:
        logger.error("Error calling fn.%s(%s)", fn_name, raw_args_str)
        logger.debug("Traceback:", exc_info=True)
        return _UNRESOLVED


# ---------------------------------------------------------------------------
# Core token resolution
# ---------------------------------------------------------------------------


def _lookup_data_entry(
    data_cache: dict[str, Any], parts: list[str]
) -> tuple[Any, list[str]]:
    """Resolve a ``{data.*}`` token against the data-source cache.

    Two cache shapes are supported so that single-domain and multi-domain
    callers share the same interpolation pipeline:

    * **Flat / current-domain:** ``{entity_type: {source_name: data}}``.
      Matches tokens of the form ``data.entity.source[.field...]``.
    * **Domain-scoped:** ``{domain: {entity_type: {source_name: data}}}``.
      Matches tokens of the form ``data.domain.entity.source[.field...]``.

    The heuristic is: prefer the domain-scoped interpretation when the
    token has at least one post-``data`` segment more than the flat form
    *and* the first two segments happen to name a real (domain, entity)
    pair in the cache.  Otherwise fall back to the flat shape.  This
    keeps the caller free of cache-shape knowledge.

    Args:
        data_cache: Either cache shape described above.
        parts: Token split on ``.``; ``parts[0]`` is ``"data"``.

    Returns:
        ``(data_entry, field_path_parts)``.  ``data_entry`` is ``None``
        when no matching entry is found; callers should treat that as
        unresolved.
    """
    # Domain-scoped interpretation: data.<domain>.<entity>.<source>[.field...]
    if (
        len(parts) >= 5
        and parts[1] in data_cache
        and isinstance(data_cache.get(parts[1]), dict)
        and parts[2] in data_cache[parts[1]]
    ):
        domain_cache = data_cache[parts[1]]
        entity_cache = domain_cache.get(parts[2])
        if isinstance(entity_cache, dict):
            return entity_cache.get(parts[3]), parts[4:]

    # Flat / current-domain interpretation: data.<entity>.<source>[.field...]
    entity_cache = data_cache.get(parts[1])
    if isinstance(entity_cache, dict):
        return entity_cache.get(parts[2]), parts[3:]

    return None, parts[3:]


def _resolve_token_inner(token: str, ctx: "InterpolationContext") -> Any:
    """Resolve a single ``scope.path`` token string (no fn.* handling).

    Returns ``_UNRESOLVED`` if the token cannot be resolved with the
    current context.
    """
    parts = token.split(".")

    # --- {var.name} ---
    if parts[0] == "var" and len(parts) >= 2:
        key = ".".join(parts[1:])
        if key in ctx.variables:
            return ctx.variables[key]
        return _UNRESOLVED

    # --- {each.key}, {each.value}, {each.value.field}, {each.index} ---
    if parts[0] == "each" and ctx.for_each is not None:
        if len(parts) >= 2 and parts[1] == "key":
            return ctx.for_each.get("key", _UNRESOLVED)
        if len(parts) >= 2 and parts[1] == "index":
            # ``each.index`` is the 0-based ordinal of the iteration.
            # Always populated by the loader for both ``count`` and
            # ``for_each`` expansions; duplicates ``each.value`` for
            # count-derived maps to match Terraform's ``count.index``.
            return ctx.for_each.get("index", _UNRESOLVED)
        if len(parts) >= 2 and parts[1] == "value":
            value = ctx.for_each.get("value", _UNRESOLVED)
            if value is _UNRESOLVED:
                return _UNRESOLVED
            return _walk_path(value, parts[2:])
        return _UNRESOLVED

    # --- {data.entity.name.field_path} ---
    # --- {data.domain.entity.name.field_path} ---
    if parts[0] == "data" and len(parts) >= 4:
        data_entry, field_path = _lookup_data_entry(ctx.data_cache, parts)
        if data_entry is None:
            return _UNRESOLVED
        return _walk_path(data_entry, field_path)

    # --- {domain.resource_name.field_path} (cross-domain) ---
    if len(parts) >= 3 and parts[0] in ctx.domain_states:
        domain = parts[0]
        resource_name = parts[1]
        field_path = parts[2:]
        resource = ctx.domain_states[domain].get(resource_name)
        if resource is None:
            return _UNRESOLVED
        return _walk_path(resource, field_path)

    # --- {resource_name.field_path} (same domain) ---
    if len(parts) >= 2:
        resource_name = parts[0]
        field_path = parts[1:]
        resource = ctx.resource_state.get(resource_name)
        if resource is not None:
            result = _walk_path(resource, field_path)
            if result is not _UNRESOLVED:
                return result
        return _UNRESOLVED

    return _UNRESOLVED


def _resolve_token(token: str, ctx: InterpolationContext, _depth: int = 0) -> Any:
    """Resolve a single interpolation token (including ``fn.*`` calls).

    Nested sub-tokens (e.g. ``{fn.pad(each.value, 2)}`` inside a
    ``{data.*}`` reference) are resolved first so that the outer
    token becomes a simple dotted path before resolution.

    When inner sub-tokens are resolved but the outer token cannot be
    (e.g. ``{data.*}`` without a data cache), the partially-resolved
    token is returned as a string ``"{resolved_token}"`` so that a
    later resolution pass can finish the job.

    Returns ``_UNRESOLVED`` if the token cannot be resolved with the
    current context or if the nested-token recursion exceeds
    ``_MAX_TOKEN_DEPTH`` (guards against runaway expansion).
    """
    if _depth >= _MAX_TOKEN_DEPTH:
        logger.error(
            "Interpolation recursion depth exceeded (%d) for token: %s",
            _MAX_TOKEN_DEPTH,
            token,
        )
        return _UNRESOLVED

    inner_resolved = False

    # Pre-resolve nested sub-tokens like {fn.pad(each.value, 2)}
    if "{" in token:
        original_token = token

        def _inner_replacer(m: re.Match) -> str:  # type: ignore[type-arg]
            resolved = _resolve_token(m.group(1), ctx, _depth=_depth + 1)
            if resolved is _UNRESOLVED:
                return m.group(0)
            return str(resolved)

        token = _TOKEN_PATTERN.sub(_inner_replacer, token)
        if "{" in token:
            return _UNRESOLVED
        inner_resolved = token != original_token

    # --- {fn.name(args)} ---
    if token.startswith("fn."):
        return _resolve_fn_call(token, ctx, _depth=_depth + 1)

    result = _resolve_token_inner(token, ctx)
    if result is _UNRESOLVED and inner_resolved:
        return f"{{{token}}}"
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve(
    data: Any,
    ctx: InterpolationContext,
    strict: bool = False,
    *,
    _depth: int = 0,
) -> Any:
    """Recursively walk *data* and resolve ``{token}`` strings.

    The private ``_depth`` kwarg threads the *token-resolution* depth
    from ``_resolve_fn_call`` (e.g. ``fn.template`` bodies) through
    nested ``resolve`` invocations so circular templates cannot blow
    the stack.  Dict/list traversal does **not** increment the depth
    counter — only token recursion does.

    Args:
        data: Any JSON-compatible structure (dict, list, str, number, bool,
            None).
        ctx: The interpolation context with all available scopes.
        strict: When ``True``, raise ``ValueError`` for any token that
            cannot be resolved.

    Returns:
        A *new* structure with all resolvable tokens replaced.  The
        original *data* is never mutated.

    Raises:
        ValueError: If *strict* is ``True`` and an unresolvable token
            is encountered, or if the interpolation recursion depth
            exceeds ``_MAX_TOKEN_DEPTH``.
    """
    if isinstance(data, str):
        # Fast-path: no tokens at all
        if "{" not in data:
            return data

        if _depth >= _MAX_TOKEN_DEPTH:
            message = (
                f"Interpolation recursion depth exceeded ({_MAX_TOKEN_DEPTH}); "
                "check for circular template includes or deeply nested tokens."
            )
            if strict:
                raise ValueError(message)
            logger.error(message)
            return data

        # Full-string token -> preserve the resolved Python type (int, dict, ...)
        full_match = _TOKEN_PATTERN.fullmatch(data)
        if full_match:
            resolved = _resolve_token(full_match.group(1), ctx, _depth=_depth + 1)
            if resolved is _UNRESOLVED:
                if strict:
                    raise ValueError(
                        f"Unresolved interpolation token: {{{full_match.group(1)}}}"
                    )
                return data
            return resolved

        # Embedded tokens -> always stringify resolved values
        def _replacer(m: re.Match) -> str:  # type: ignore[type-arg]
            resolved = _resolve_token(m.group(1), ctx, _depth=_depth + 1)
            if resolved is _UNRESOLVED:
                if strict:
                    raise ValueError(
                        f"Unresolved interpolation token: {{{m.group(1)}}}"
                    )
                return m.group(0)
            return str(resolved)

        return _TOKEN_PATTERN.sub(_replacer, data)

    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for k, v in data.items():
            resolved_key = resolve(k, ctx, strict=strict, _depth=_depth)
            if not isinstance(resolved_key, str):
                if strict:
                    raise ValueError(
                        f"Dict key resolved to non-string type "
                        f"{type(resolved_key).__name__}: {k!r}"
                    )
                resolved_key = str(resolved_key)
            result[resolved_key] = resolve(v, ctx, strict=strict, _depth=_depth)
        return result

    if isinstance(data, list):
        return [resolve(item, ctx, strict=strict, _depth=_depth) for item in data]

    # Numbers, bools, None -> pass through
    return data


_SCOPED_PREFIXES = frozenset({"var", "each", "data", "fn"})


def has_tokens(data: Any) -> bool:
    """Return ``True`` if *data* contains any ``{...}`` interpolation tokens."""
    if isinstance(data, str):
        return bool(_TOKEN_PATTERN.search(data))
    if isinstance(data, dict):
        return any(has_tokens(k) or has_tokens(v) for k, v in data.items())
    if isinstance(data, list):
        return any(has_tokens(item) for item in data)
    return False


def _iter_tokens(data: Any) -> Iterator[tuple[str, list[str]]]:
    """Yield ``(token, parts)`` for every ``{...}`` token in *data*.

    Walks dicts (both keys and values), lists, and strings.  Non-container,
    non-string leaves are skipped.  The returned ``parts`` list is the
    token split on ``.`` so callers avoid redundant splitting.

    Used by :func:`classify_unresolved_tokens`,
    :func:`extract_resource_refs`, and :func:`extract_cross_domain_refs`
    to avoid three structurally-identical recursive walkers.
    """
    if isinstance(data, str):
        if "{" not in data:
            return
        for match in _TOKEN_PATTERN.finditer(data):
            token = match.group(1)
            yield token, token.split(".")
    elif isinstance(data, dict):
        for key, value in data.items():
            yield from _iter_tokens(key)
            yield from _iter_tokens(value)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_tokens(item)


def classify_unresolved_tokens(
    data: Any,
    known_resources: set[str] | None = None,
    known_domains: set[str] | None = None,
) -> tuple[set[str], set[str]]:
    """Partition unresolved tokens into resource-refs and other failures.

    Args:
        data: Any JSON-compatible structure.
        known_resources: Resource names in the current domain.
        known_domains: Domain names from config (for cross-domain refs).

    Returns:
        ``(resource_ref_tokens, failed_tokens)`` where *resource_ref_tokens*
        are ``{resource_name.field}`` patterns that will resolve at apply
        time, and *failed_tokens* are everything else (data sources, vars,
        etc.) that indicate a real problem.
    """
    resource_refs: set[str] = set()
    failures: set[str] = set()
    known = known_resources or set()
    domains = known_domains or set()

    for token, parts in _iter_tokens(data):
        if parts[0] in _SCOPED_PREFIXES:
            failures.add(token)
            continue
        is_local_ref = parts[0] in known and len(parts) >= 2
        is_cross_domain_ref = parts[0] in domains and len(parts) >= 3
        if is_local_ref or is_cross_domain_ref:
            resource_refs.add(token)
        else:
            failures.add(token)

    return resource_refs, failures


def extract_resource_refs(data: Any, known_resources: set[str]) -> set[str]:
    """Return resource names referenced by interpolation tokens in *data*.

    Only tokens matching the ``{resource_name.field}`` pattern are
    considered, and only if *resource_name* is in *known_resources*.
    Scoped tokens (``var.*``, ``each.*``, ``data.*``, ``fn.*``) are
    skipped.

    Args:
        data: Any JSON-compatible structure (dict, list, str, ...).
        known_resources: Set of valid resource names in the current domain.

    Returns:
        Set of resource names from *known_resources* that appear as
        interpolation references in *data*.
    """
    return {
        parts[0]
        for _, parts in _iter_tokens(data)
        if len(parts) >= 2
        and parts[0] not in _SCOPED_PREFIXES
        and parts[0] in known_resources
    }


def extract_cross_domain_refs(data: Any, known_domains: set[str]) -> set[str]:
    """Return domain names referenced by cross-domain interpolation tokens.

    Tokens matching ``{domain.resource.field}`` where *domain* is in
    *known_domains* are detected.  Scoped prefixes (``var``, ``data``,
    ``fn``, ``each``) are excluded.

    Args:
        data: Any JSON-compatible structure.
        known_domains: Set of valid domain names from config.

    Returns:
        Set of domain names that appear as cross-domain references.
    """
    return {
        parts[0]
        for _, parts in _iter_tokens(data)
        if len(parts) >= 3
        and parts[0] not in _SCOPED_PREFIXES
        and parts[0] in known_domains
    }
