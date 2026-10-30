"""Runtime lookup for reviewed legacy registry corrections."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import orjson

_Correction = TypeVar("_Correction")


@dataclass(frozen=True, slots=True)
class MovedOperationCorrection:
    """Replacement for an operation invoked through its released owner."""

    legacy_owner: str
    canonical_owner: str
    operation: str
    behavior: str


@dataclass(frozen=True, slots=True)
class FalseCrudCorrection:
    """Replacement for an action formerly exposed as CRUD lifecycle."""

    legacy_entity: str
    legacy_lifecycle_role: str
    canonical_entity: str
    operation: str
    behavior: str


@dataclass(frozen=True, slots=True)
class RemovedEntityCorrection:
    """Compatibility behavior for a removed public entity."""

    entity: str
    namespace: str
    behavior: str
    reason: str
    replacement: str | None


class RegistryCorrections:
    """Indexed compatibility behavior from the generated correction registry."""

    def __init__(self, document: dict[str, object]) -> None:
        """Build immutable lookup indexes from generated metadata.

        Args:
            document: Parsed ``registry_corrections.json`` document.

        Raises:
            ValueError: If required correction fields are malformed.
        """
        self._moved_operations = self._index_moved_operations(document)
        self._false_crud = self._index_false_crud(document)
        self._removed_entities = self._index_removed_entities(document)

    def moved_operation(
        self,
        entity: str,
        operation_name: str,
    ) -> MovedOperationCorrection | None:
        """Return a correction for released operation-owner syntax.

        Args:
            entity: Released entity owner.
            operation_name: Released public or SDK operation spelling.

        Returns:
            Reviewed correction, or ``None`` when the binding is canonical.
        """
        return self._moved_operations.get((entity, operation_name))

    def false_crud(
        self,
        entity: str,
        lifecycle_role: str,
    ) -> FalseCrudCorrection | None:
        """Return a correction for released false-CRUD lifecycle syntax.

        Args:
            entity: Released entity owner.
            lifecycle_role: Released CRUD slot.

        Returns:
            Reviewed correction, or ``None`` when the lifecycle slot is valid.
        """
        return self._false_crud.get((entity, lifecycle_role))

    def removed_entity(
        self,
        entity: str,
    ) -> RemovedEntityCorrection | None:
        """Return compatibility behavior for a removed public entity.

        Args:
            entity: Released public entity name.

        Returns:
            Reviewed removal tombstone, or ``None`` for an active entity.
        """
        return self._removed_entities.get(entity)

    @staticmethod
    def _index_moved_operations(
        document: dict[str, object],
    ) -> dict[tuple[str, str], MovedOperationCorrection]:
        raw_corrections = _mapping(
            document.get("operation_owner_changes"),
            "operation owner changes",
        )
        index: dict[tuple[str, str], MovedOperationCorrection] = {}
        for raw_value in raw_corrections.values():
            value = _mapping(raw_value, "operation owner correction")
            correction = MovedOperationCorrection(
                legacy_owner=_string(value.get("legacy_owner"), "legacy_owner"),
                canonical_owner=_string(
                    value.get("canonical_owner"),
                    "canonical_owner",
                ),
                operation=_string(value.get("operation"), "operation"),
                behavior=_string(
                    value.get("legacy_behavior"),
                    "legacy_behavior",
                ),
            )
            for operation_name in _string_list(
                value.get("legacy_operation_names"),
                "legacy_operation_names",
            ):
                key = (correction.legacy_owner, operation_name)
                _insert_unique(index, key, correction)
        return index

    @staticmethod
    def _index_false_crud(
        document: dict[str, object],
    ) -> dict[tuple[str, str], FalseCrudCorrection]:
        raw_corrections = _mapping(document.get("false_crud"), "false CRUD")
        index: dict[tuple[str, str], FalseCrudCorrection] = {}
        for raw_value in raw_corrections.values():
            value = _mapping(raw_value, "false CRUD correction")
            replacement = _mapping(value.get("replacement"), "replacement")
            correction = FalseCrudCorrection(
                legacy_entity=_string(
                    value.get("legacy_entity"),
                    "legacy_entity",
                ),
                legacy_lifecycle_role=_string(
                    value.get("legacy_lifecycle_slot"),
                    "legacy_lifecycle_slot",
                ),
                canonical_entity=_string(
                    replacement.get("entity"),
                    "replacement entity",
                ),
                operation=_string(
                    replacement.get("operation"),
                    "replacement operation",
                ),
                behavior=_string(
                    value.get("legacy_behavior"),
                    "legacy_behavior",
                ),
            )
            key = (
                correction.legacy_entity,
                correction.legacy_lifecycle_role,
            )
            _insert_unique(index, key, correction)
        return index

    @staticmethod
    def _index_removed_entities(
        document: dict[str, object],
    ) -> dict[str, RemovedEntityCorrection]:
        raw_corrections = _mapping(
            document.get("removed_entities", {}),
            "removed entities",
        )
        index: dict[str, RemovedEntityCorrection] = {}
        for entity, raw_value in raw_corrections.items():
            value = _mapping(raw_value, "removed entity correction")
            behavior = _string(value.get("behavior"), "behavior")
            if behavior != "warn_and_reject":
                raise ValueError(f"Unsupported removed entity behavior: {behavior}")
            correction = RemovedEntityCorrection(
                entity=entity,
                namespace=_string(value.get("namespace"), "namespace"),
                behavior=behavior,
                reason=_string(value.get("reason"), "reason"),
                replacement=_optional_string(
                    value.get("replacement"),
                    "replacement",
                ),
            )
            index[entity] = correction
        return index


@lru_cache(maxsize=1)
def load_registry_corrections() -> RegistryCorrections:
    """Load and cache packaged legacy correction metadata.

    Returns:
        Validated correction lookup.

    Raises:
        OSError: If the packaged correction document cannot be read.
        orjson.JSONDecodeError: If the document is invalid JSON.
        ValueError: If the correction shape is invalid.
    """
    path = Path(__file__).with_name("registry_corrections.json")
    document = orjson.loads(path.read_bytes())
    return RegistryCorrections(_mapping(document, "registry corrections"))


def _insert_unique(
    index: dict[tuple[str, str], _Correction],
    key: tuple[str, str],
    value: _Correction,
) -> None:
    previous = index.setdefault(key, value)
    if previous != value:
        raise ValueError(f"Conflicting registry correction: {key}")


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a string-keyed mapping")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{label} must be a string list")
    return tuple(value)
