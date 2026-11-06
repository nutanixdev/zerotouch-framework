"""Runtime access to the generated entity and operation catalog."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import orjson


@dataclass(frozen=True, slots=True)
class RuntimeOperation:
    """Exact runtime adapter selected for one public operation."""

    key: str
    canonical_entity: str
    public_name: str
    operation_id: str
    kind: str
    lifecycle_role: str | None
    package: str
    module: str
    api_class: str
    method: str


class RuntimeCatalog:
    """Validated in-memory lookup over the generated catalog document."""

    def __init__(self, document: dict[str, object]) -> None:
        """Initialize indexed runtime lookups.

        Args:
            document: Parsed generated ``entity_catalog.json`` document.

        Raises:
            ValueError: If the generated document has an invalid shape.
        """
        self._entities = _mapping(document.get("entities"), "entities")
        self._aliases = _mapping(document.get("aliases"), "aliases")
        self._operations = _mapping(document.get("operations"), "operations")
        self._method_index = self._build_method_index()

    def resolve_entity(self, name: str) -> str | None:
        """Resolve an entity or released alias to its canonical name.

        Args:
            name: User-facing entity name.

        Returns:
            Canonical name, or ``None`` when the entity is unknown.
        """
        alias = self._aliases.get(name)
        if alias is not None:
            return _string(
                _mapping(alias, f"alias {name}").get("canonical_name"),
                f"alias {name} canonical_name",
            )
        return name if name in self._entities else None

    def is_entity_alias(self, name: str) -> bool:
        """Return whether a name is a released deprecated alias.

        Args:
            name: User-facing entity name.

        Returns:
            ``True`` when the name is a generated compatibility alias.
        """
        return name in self._aliases

    def resolve_lifecycle(
        self,
        entity: str,
        lifecycle_role: str,
    ) -> RuntimeOperation | None:
        """Resolve an entity lifecycle slot to its exact adapter.

        Args:
            entity: Canonical entity or released alias.
            lifecycle_role: CRUD role such as ``create`` or ``get``.

        Returns:
            Exact runtime operation, or ``None`` when unsupported.
        """
        canonical, document = self._entity_document(entity)
        if canonical is None or document is None:
            return None
        lifecycle = _mapping(document.get("lifecycle"), "entity lifecycle")
        operation_key = lifecycle.get(lifecycle_role)
        if not isinstance(operation_key, str):
            return None
        return self._runtime_operation(canonical, operation_key)

    def resolve_operation(
        self,
        entity: str,
        operation_name: str,
    ) -> RuntimeOperation | None:
        """Resolve a public operation key or compatible SDK-method alias.

        Args:
            entity: Canonical entity or released alias.
            operation_name: Public key or released operation spelling.

        Returns:
            Exact runtime operation, or ``None`` when unsupported.
        """
        canonical, document = self._entity_document(entity)
        if canonical is None or document is None:
            return None
        aliases = _mapping(
            document.get("operation_aliases"),
            "operation aliases",
        )
        public_name = aliases.get(operation_name, operation_name)
        if not isinstance(public_name, str):
            return None
        operations = _mapping(document.get("operations"), "entity operations")
        operation_key = operations.get(public_name)
        if not isinstance(operation_key, str):
            return None
        return self._runtime_operation(canonical, operation_key)

    def resolve_method(
        self,
        entity: str,
        sdk_method: str,
    ) -> RuntimeOperation | None:
        """Resolve an exact SDK method within one canonical entity.

        Args:
            entity: Canonical entity or released alias.
            sdk_method: Exact generated Python SDK method name.

        Returns:
            Exact runtime operation, or ``None`` when unsupported.
        """
        canonical = self.resolve_entity(entity)
        if canonical is None:
            return None
        operation_key = self._method_index.get((canonical, sdk_method))
        if operation_key is None:
            return None
        return self._runtime_operation(canonical, operation_key)

    def _entity_document(
        self,
        entity: str,
    ) -> tuple[str | None, dict[str, object] | None]:
        canonical = self.resolve_entity(entity)
        if canonical is None:
            return None, None
        return canonical, _mapping(
            self._entities.get(canonical),
            f"entity {canonical}",
        )

    def _runtime_operation(
        self,
        canonical_entity: str,
        operation_key: str,
    ) -> RuntimeOperation:
        document = _mapping(
            self._operations.get(operation_key),
            f"operation {operation_key}",
        )
        adapter = _mapping(document.get("adapter"), "operation adapter")
        return RuntimeOperation(
            key=operation_key,
            canonical_entity=canonical_entity,
            public_name=_string(document.get("public_name"), "public_name"),
            operation_id=_string(document.get("operation_id"), "operation_id"),
            kind=_string(document.get("kind"), "kind"),
            lifecycle_role=_optional_string(document.get("lifecycle_role")),
            package=_string(adapter.get("package"), "adapter package"),
            module=_string(adapter.get("module"), "adapter module"),
            api_class=_string(adapter.get("api_class"), "adapter api_class"),
            method=_string(adapter.get("method"), "adapter method"),
        )

    def _build_method_index(self) -> dict[tuple[str, str], str]:
        index: dict[tuple[str, str], str] = {}
        for raw_operation_key, raw_document in self._operations.items():
            operation_key = _string(raw_operation_key, "operation key")
            document = _mapping(raw_document, f"operation {operation_key}")
            owner = _string(document.get("owner"), "operation owner")
            adapter = _mapping(document.get("adapter"), "operation adapter")
            method = _string(adapter.get("method"), "adapter method")
            key = (owner, method)
            previous = index.setdefault(key, operation_key)
            if previous != operation_key:
                raise ValueError(
                    f"Duplicate SDK method {owner}.{method} in runtime catalog"
                )
        return index


@lru_cache(maxsize=1)
def load_runtime_catalog() -> RuntimeCatalog:
    """Load and cache the generated runtime entity catalog.

    Returns:
        Validated runtime catalog.

    Raises:
        OSError: If the packaged catalog cannot be read.
        orjson.JSONDecodeError: If the catalog is invalid JSON.
        ValueError: If the catalog shape is invalid.
    """
    path = Path(__file__).with_name("entity_catalog.json")
    document = orjson.loads(path.read_bytes())
    return RuntimeCatalog(_mapping(document, "entity catalog"))


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a string-keyed mapping")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value, "optional string")
