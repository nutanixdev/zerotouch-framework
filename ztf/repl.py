"""REPL support for ZTF: data namespace, entity client, and execution context."""

from __future__ import annotations

import code
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from ztf.entity_wrapper.entity_handler import DomainEntityHandler
from ztf.entity_wrapper.entity_map import entity_map as entity_metadata_map
from ztf.utils.utils import strip_internal_attributes


class EntityHandlerProtocol(Protocol):
    """Protocol for entity handlers used by the REPL data namespace."""

    def list_entities(
        self, entity: str, _filter: str | None = None, **kwargs: object
    ) -> list[object]:
        """List entities of the given type."""
        ...

    def get_entity_by_identifier(
        self, entity: str, _filter: str | None, **kwargs: object
    ) -> tuple[object | None, str | None]:
        """Get entity by filter expression."""
        ...

    def get_entity_by_ext_id(
        self, entity: str, ext_id: str, **kwargs: object
    ) -> object | None:
        """Get entity by external ID."""
        ...

    def sanitize_entity_data(self, entity: str, data: object) -> object:
        """Sanitize entity data for display."""
        ...


def _serialize_entity(
    handler: EntityHandlerProtocol, entity: str, item: dict[str, object] | object
) -> dict[str, object]:
    """Convert an entity item to a sanitized dict suitable for REPL display.

    Args:
        handler: The domain entity handler for sanitization.
        entity: The entity type name.
        item: Raw entity data (dict or SDK object).

    Returns:
        A dict with internal attributes stripped, safe for display/serialization.

    Raises:
        ValueError: If the handler reports invalid data (e.g. None).
    """
    sanitized: object
    if isinstance(item, dict):
        sanitized = deepcopy(item)
    else:
        sanitized = handler.sanitize_entity_data(entity, item)
    return cast(dict[str, object], strip_internal_attributes(sanitized))


def _resolve_domain(
    handlers: dict[str, EntityHandlerProtocol],
    domain: str | None,
    default_domain: str | None,
) -> str:
    """Resolve which domain to use for an operation.

    Args:
        handlers: Map of domain name -> handler.
        domain: Explicit domain from the caller, or None.
        default_domain: Default domain when none specified.

    Returns:
        The resolved domain name.

    Raises:
        ValueError: If domain is unknown or ambiguous (multiple domains, no default).
    """
    if domain:
        if domain not in handlers:
            raise ValueError(f"Unknown domain: {domain}")
        return domain
    if default_domain:
        return default_domain
    if len(handlers) == 1:
        return next(iter(handlers))
    raise ValueError("Domain is required when multiple domains are configured.")


class DataEntityClient:
    """Client for listing and fetching entities of a single type across domains."""

    def __init__(
        self,
        entity: str,
        handlers: dict[str, EntityHandlerProtocol],
        default_domain: str | None,
    ) -> None:
        """Initialize the entity client.

        Args:
            entity: The entity type name (e.g. ``cluster``, ``vm``).
            handlers: Map of domain name -> handler.
            default_domain: Default domain when none specified.
        """
        self._entity = entity
        self._handlers = handlers
        self._default_domain = default_domain

    def list(
        self,
        *,
        domain: str | None = None,
        filter: str | None = None,  # noqa: A002
        **kwargs: object,
    ) -> list[dict[str, object]]:
        """List entities of this type.

        Args:
            domain: Optional domain override.
            filter: Optional filter expression for the list API.
            **kwargs: Additional arguments passed to the list method.

        Returns:
            List of sanitized entity dicts.

        Raises:
            ValueError: If domain is unknown or ambiguous.
        """
        domain_name = _resolve_domain(self._handlers, domain, self._default_domain)
        handler = self._handlers[domain_name]
        items = handler.list_entities(self._entity, _filter=filter, **kwargs)
        return [_serialize_entity(handler, self._entity, item) for item in items]

    def get(
        self,
        *,
        domain: str | None = None,
        filter: str | None = None,  # noqa: A002
        ext_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object] | None:
        """Get a single entity by filter or external ID.

        Args:
            domain: Optional domain override.
            filter: Filter expression to identify the entity.
            ext_id: External ID of the entity.
            **kwargs: Additional arguments passed to the get method.

        Returns:
            Sanitized entity dict, or None if not found.

        Raises:
            ValueError: If neither filter nor ext_id is provided, or if domain
                is unknown or ambiguous.
        """
        domain_name = _resolve_domain(self._handlers, domain, self._default_domain)
        handler = self._handlers[domain_name]
        if filter:
            item, _ = handler.get_entity_by_identifier(
                self._entity, _filter=filter, **kwargs
            )
        elif ext_id:
            item = handler.get_entity_by_ext_id(self._entity, ext_id, **kwargs)
        else:
            raise ValueError("Either filter or ext_id must be provided.")
        if not item:
            return None
        return _serialize_entity(handler, self._entity, item)


class DataNamespace:
    """Namespace providing entity clients via attribute access (e.g. ``data.cluster``)."""

    def __init__(
        self,
        handlers: dict[str, EntityHandlerProtocol],
        default_domain: str | None = None,
    ) -> None:
        """Initialize the data namespace.

        Args:
            handlers: Map of domain name -> handler.
            default_domain: Default domain when multiple domains exist.
        """
        self._handlers = handlers
        self._default_domain = default_domain

    def __getattr__(self, entity: str) -> DataEntityClient:
        """Return a DataEntityClient for the given entity type.

        Args:
            entity: The entity type name (e.g. ``cluster``, ``vm``).

        Returns:
            A DataEntityClient bound to this namespace and the given entity.
        """
        return DataEntityClient(entity, self._handlers, self._default_domain)


@dataclass(frozen=True)
class ReplContext:
    """Immutable context for REPL execution: config, handlers, and data namespace.

    Attributes:
        global_config: Top-level ZTF configuration (e.g. from input.yml root).
        config: Domain-specific or namespace-specific configuration.
        handlers: Map of domain name to DomainEntityHandler for entity operations.
        data: DataNamespace providing entity clients (e.g. ctx.data.cluster).
        default_domain: Default domain when multiple domains are configured.
    """

    global_config: dict[str, object]
    config: dict[str, object]
    handlers: dict[str, DomainEntityHandler]
    data: DataNamespace
    default_domain: str | None

    def to_locals(self) -> dict[str, object]:
        """Return a dict suitable for use as REPL locals (e.g. ``exec(..., to_locals())``).

        Returns:
            Dict with ``ctx`` (this ReplContext) and ``data`` (DataNamespace)
            for use as ``exec(code, globals(), ctx.to_locals())``.
        """
        return {"ctx": self, "data": self.data}


def build_repl_context(
    global_config: dict[str, object], config: dict[str, object]
) -> ReplContext:
    """Build REPL context from global and domain config.

    Creates DomainEntityHandler instances per host (shared when multiple
    domains use the same host), a DataNamespace for entity access, and
    computes the default domain.

    Args:
        global_config: Top-level ZTF configuration (e.g. from global.yml).
        config: Loaded config with domains (from load_config).

    Returns:
        ReplContext with handlers, data namespace, and default_domain.

    Raises:
        ValueError: If a domain lacks credentials or has no entities.
    """
    raw_domains = config.get("domains", {})
    if not isinstance(raw_domains, dict):
        raise ValueError("Config 'domains' must be a dict.")
    domains = cast(dict[str, dict[str, object]], raw_domains)
    if not domains:
        raise ValueError("Config must have at least one domain.")

    domain_name_to_host: dict[str, str] = {}
    domain_global_config_map: dict[str, dict[str, object]] = {}
    created_hosts: set[str] = set()
    handlers: dict[str, DomainEntityHandler] = {}

    for domain_name, domain_cfg in domains.items():
        host = str(domain_cfg.get("host", domain_name))
        username = domain_cfg.get("username", "")
        password = domain_cfg.get("password", "")

        if not username or not password:
            raise ValueError(
                f"Domain '{domain_name}' must include 'username' and 'password'."
            )

        domain_name_to_host[domain_name] = host
        domain_api_config = dict(deepcopy(global_config))
        config_section = domain_api_config.get("config")
        if not isinstance(config_section, dict):
            config_section = {}
        config_section = dict(config_section)
        config_section["host"] = host
        config_section["username"] = username
        config_section["password"] = password
        domain_api_config["config"] = config_section
        domain_global_config_map[domain_name] = domain_api_config

        resources = domain_cfg.get("resources", {})
        data_sources = domain_cfg.get("data", {})
        entity_keys: set[str] = set()
        if isinstance(resources, dict):
            entity_keys = {str(k) for k in resources}
        if isinstance(data_sources, dict):
            entity_keys |= {str(k) for k in data_sources}

        if not entity_keys:
            continue

        if host in created_hosts:
            for dn, handler in handlers.items():
                if domain_name_to_host.get(dn) == host:
                    handlers[domain_name] = handler
                    break
        else:
            handler = DomainEntityHandler(
                entity_keys,
                global_config_data=domain_api_config,
                entity_metadata_map=deepcopy(entity_metadata_map),
            )
            handlers[domain_name] = handler
            created_hosts.add(host)

    if not handlers:
        raise ValueError(
            "No domains with resources or data sources. "
            "Add at least one entity under resources or data."
        )

    default_domain = next(iter(handlers)) if len(handlers) == 1 else None
    protocol_handlers = cast(dict[str, EntityHandlerProtocol], handlers)
    data = DataNamespace(protocol_handlers, default_domain)

    return ReplContext(
        global_config=global_config,
        config=config,
        handlers=handlers,
        data=data,
        default_domain=default_domain,
    )


def start_repl(
    locals_dict: dict[str, object],
    exec_code: str | None = None,
    script_path: str | None = None,
) -> None:
    """Start the REPL: exec code, run script, or interactive session.

    Args:
        locals_dict: Dict with ``ctx`` and ``data`` for use as exec locals.
        exec_code: One-line code to execute (e.g. from --exec).
        script_path: Path to a Python script to execute (e.g. from --script).
    """
    if exec_code is not None:
        exec(exec_code, globals(), locals_dict)  # noqa: S102  # nosec B102
    elif script_path is not None:
        path = Path(script_path)
        code_str = path.read_text(encoding="utf-8")
        exec(code_str, globals(), locals_dict)  # noqa: S102  # nosec B102
    else:
        code.interact(local=locals_dict)
