"""Optional one-time migration for reviewed entity-registry corrections."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import orjson
import yaml

_DATA_TOKEN = re.compile(r"\{data\.[^{}]+\}")


class MigrationError(ValueError):
    """Raised when a migration cannot prove a safe all-or-nothing transform."""


@dataclass(frozen=True, slots=True)
class MigrationChange:
    """One deterministic configuration or state correction."""

    kind: str
    document: str
    domain: str
    source: str
    target: str
    resource_name: str | None = None


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """In-memory one-time migration result."""

    input_config: dict[str, Any]
    state: dict[str, Any]
    changes: tuple[MigrationChange, ...]

    @property
    def changed(self) -> bool:
        """Return whether any reviewed transform applied."""
        return bool(self.changes)


@dataclass(frozen=True, slots=True)
class _OwnerMove:
    """One reviewed operation-owner transform within a domain."""

    domain: str
    legacy_owner: str
    canonical_owner: str
    legacy_names: frozenset[str]
    public_operation: str


@dataclass(frozen=True, slots=True)
class _FalseCrudTransform:
    """Resolved false-CRUD migration parameters."""

    legacy_entity: str
    canonical_entity: str
    operation_name: str
    state_behavior: str
    unsupported_files: bool
    migration: dict[str, object]


@dataclass(frozen=True, slots=True)
class _MigrationFiles:
    """Original and migrated byte pairs for transactional persistence."""

    input_path: Path
    state_path: Path
    original_input: bytes
    original_state: bytes
    migrated_input: bytes
    migrated_state: bytes


def migrate_entity_registry_documents(
    input_config: dict[str, Any],
    state: dict[str, Any],
) -> MigrationResult:
    """Apply fixed reviewed registry transforms entirely in memory.

    Args:
        input_config: Raw parsed ZTF input configuration.
        state: Raw parsed ZTF managed state.

    Returns:
        Migrated deep copies and an ordered change ledger.

    Raises:
        MigrationError: If a merge or false-CRUD state transform is ambiguous.
    """
    migrated_input = copy.deepcopy(input_config)
    migrated_state = copy.deepcopy(state)
    _validate_document(migrated_input, "input configuration", require_domains=True)
    _validate_document(migrated_state, "state", require_domains=False)
    corrections = _load_correction_document()
    changes: list[MigrationChange] = []
    _migrate_entity_aliases(
        migrated_input,
        migrated_state,
        corrections,
        changes,
    )
    _migrate_operation_owners(migrated_input, corrections, changes)
    _migrate_false_crud(
        migrated_input,
        migrated_state,
        corrections,
        changes,
    )
    _validate_document(migrated_input, "migrated input", require_domains=True)
    _validate_document(migrated_state, "migrated state", require_domains=False)
    return MigrationResult(
        input_config=migrated_input,
        state=migrated_state,
        changes=tuple(changes),
    )


def run_entity_registry_migration(
    input_path: Path,
    state_path: Path,
    *,
    write: bool,
) -> dict[str, object]:
    """Run dry-run or transactional write-mode migration for two YAML files.

    Args:
        input_path: Existing ``input.yml`` path.
        state_path: Existing managed ``state.yml`` path.
        write: Replace originals when true; otherwise write review siblings.

    Returns:
        Machine-readable migration report.

    Raises:
        MigrationError: If inputs are invalid, ambiguous, or change concurrently.
    """
    original_input = _read_required_file(input_path, "Input file")
    original_state = _read_required_file(state_path, "State file")
    input_document = _load_yaml_bytes(original_input, "input configuration")
    state_document = _load_yaml_bytes(original_state, "state")
    result = migrate_entity_registry_documents(input_document, state_document)
    files = _MigrationFiles(
        input_path=input_path,
        state_path=state_path,
        original_input=original_input,
        original_state=original_state,
        migrated_input=_yaml_bytes(result.input_config),
        migrated_state=_yaml_bytes(result.state),
    )
    output_paths = _persist_migration_outputs(files, result.changed, write)
    report = _migration_report(
        files,
        result,
        write,
        output_paths,
    )
    report_path = input_path.with_name("entity-registry-migration-report.json")
    _atomic_write_bytes(
        report_path, orjson.dumps(report, option=orjson.OPT_INDENT_2) + b"\n"
    )
    return report


def _persist_migration_outputs(
    files: _MigrationFiles,
    changed: bool,
    write: bool,
) -> dict[str, str]:
    if not changed:
        return {}
    if write:
        return _write_originals_transactionally(files)
    return _write_review_siblings(
        files.input_path,
        files.state_path,
        files.migrated_input,
        files.migrated_state,
    )


def _migrate_entity_aliases(
    input_config: dict[str, Any],
    state: dict[str, Any],
    corrections: dict[str, object],
    changes: list[MigrationChange],
) -> None:
    aliases = _mapping(corrections.get("entity_aliases"), "entity aliases")
    for domain_name, domain in _domains(input_config).items():
        for section_name in ("resources", "data"):
            section = _optional_mapping(domain.get(section_name), section_name)
            _rename_entity_headings(
                section,
                aliases,
                "input",
                domain_name,
                changes,
            )
    for domain_name, domain in _domains(state).items():
        resources = _optional_mapping(domain.get("resources"), "state resources")
        _rename_entity_headings(
            resources,
            aliases,
            "state",
            domain_name,
            changes,
        )
    alias_names = {
        alias: _string(
            _mapping(value, f"alias {alias}").get("canonical_name"),
            f"alias {alias} canonical name",
        )
        for alias, value in aliases.items()
    }
    _rewrite_data_tokens(input_config, alias_names, changes)


def _rewrite_data_tokens(
    input_config: dict[str, Any],
    aliases: dict[str, str],
    changes: list[MigrationChange],
) -> None:
    domains = set(_domains(input_config))

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if not isinstance(value, str):
            return value
        return _DATA_TOKEN.sub(
            lambda match: _rewrite_data_token(
                match.group(0),
                aliases,
                domains,
                changes,
            ),
            value,
        )

    rewritten = rewrite(input_config)
    input_config.clear()
    input_config.update(rewritten)


def _rewrite_data_token(
    token: str,
    aliases: dict[str, str],
    domains: set[str],
    changes: list[MigrationChange],
) -> str:
    parts = token[1:-1].split(".")
    entity_position = 2 if len(parts) >= 5 and parts[1] in domains else 1
    entity = parts[entity_position]
    canonical = aliases.get(entity)
    if canonical is None:
        return token
    parts[entity_position] = canonical
    changes.append(
        MigrationChange(
            kind="interpolation_alias",
            document="input",
            domain=parts[1] if entity_position == 2 else "*",
            source=entity,
            target=canonical,
        )
    )
    return f"{{{'.'.join(parts)}}}"


def _rename_entity_headings(
    section: dict[str, Any],
    aliases: dict[str, object],
    document: str,
    domain: str,
    changes: list[MigrationChange],
) -> None:
    for alias, raw_correction in aliases.items():
        if alias not in section:
            continue
        correction = _mapping(raw_correction, f"alias {alias}")
        canonical = _string(
            correction.get("canonical_name"),
            f"alias {alias} canonical name",
        )
        source_resources = _mapping(section.pop(alias), f"{alias} resources")
        target_resources = _optional_mapping(section.get(canonical), canonical)
        _merge_named_resources(
            target_resources,
            source_resources,
            domain,
            alias,
            canonical,
        )
        section[canonical] = target_resources
        changes.append(
            MigrationChange(
                kind="entity_alias",
                document=document,
                domain=domain,
                source=alias,
                target=canonical,
            )
        )


def _merge_named_resources(
    target: dict[str, Any],
    source: dict[str, object],
    domain: str,
    source_entity: str,
    target_entity: str,
) -> None:
    for resource_name, value in source.items():
        existing = target.get(resource_name)
        if existing is not None and existing != value:
            raise MigrationError(
                f"Cannot merge resource {resource_name!r} in domain {domain!r}: "
                f"{source_entity!r} and {target_entity!r} differ."
            )
        target[resource_name] = value


def _migrate_operation_owners(
    input_config: dict[str, Any],
    corrections: dict[str, object],
    changes: list[MigrationChange],
) -> None:
    owner_changes = _mapping(
        corrections.get("operation_owner_changes"),
        "operation owner changes",
    )
    for raw_correction in owner_changes.values():
        correction = _mapping(raw_correction, "operation owner correction")
        legacy_owner = _string(correction.get("legacy_owner"), "legacy owner")
        canonical_owner = _string(
            correction.get("canonical_owner"),
            "canonical owner",
        )
        legacy_names = set(
            _string_list(
                correction.get("legacy_operation_names"),
                "legacy operation names",
            )
        )
        public_operation = _string(correction.get("operation"), "operation")
        for domain_name, domain in _domains(input_config).items():
            resources = _optional_mapping(domain.get("resources"), "resources")
            _move_matching_operations(
                resources,
                _OwnerMove(
                    domain=domain_name,
                    legacy_owner=legacy_owner,
                    canonical_owner=canonical_owner,
                    legacy_names=frozenset(legacy_names),
                    public_operation=public_operation,
                ),
                changes,
            )


def _move_matching_operations(
    resources: dict[str, Any],
    move: _OwnerMove,
    changes: list[MigrationChange],
) -> None:
    legacy_resources = _optional_mapping(
        resources.get(move.legacy_owner),
        move.legacy_owner,
    )
    if not legacy_resources:
        return
    for resource_name in list(legacy_resources):
        resource = _mapping(
            legacy_resources[resource_name],
            f"{move.legacy_owner}.{resource_name}",
        )
        operations = _operation_list(resource)
        moved = [
            operation
            for operation in operations
            if operation.get("type") in move.legacy_names
        ]
        if not moved:
            continue
        resource["operations"] = [
            operation for operation in operations if operation not in moved
        ]
        for operation in moved:
            migrated_operation = copy.deepcopy(operation)
            migrated_operation["type"] = move.public_operation
            _append_target_operation(
                resources,
                move.canonical_owner,
                resource_name,
                resource,
                migrated_operation,
            )
            changes.append(
                MigrationChange(
                    kind="operation_owner",
                    document="input",
                    domain=move.domain,
                    source=move.legacy_owner,
                    target=move.canonical_owner,
                    resource_name=resource_name,
                )
            )
        _remove_empty_resource(legacy_resources, resource_name, resource)
    if not legacy_resources:
        resources.pop(move.legacy_owner, None)


def _append_target_operation(
    resources: dict[str, Any],
    canonical_owner: str,
    resource_name: str,
    source_resource: dict[str, object],
    operation: dict[str, object],
) -> None:
    canonical_resources = _optional_mapping(
        resources.get(canonical_owner),
        canonical_owner,
    )
    target = _optional_mapping(
        canonical_resources.get(resource_name),
        resource_name,
    )
    for metadata_key in ("rules", "depends_on"):
        if metadata_key in source_resource:
            existing = target.get(metadata_key)
            if existing is not None and existing != source_resource[metadata_key]:
                raise MigrationError(
                    f"Cannot merge {metadata_key!r} for resource {resource_name!r}."
                )
            target[metadata_key] = copy.deepcopy(source_resource[metadata_key])
    target_operations = _operation_list(target)
    if operation not in target_operations:
        target_operations.append(operation)
    target["operations"] = target_operations
    canonical_resources[resource_name] = target
    resources[canonical_owner] = canonical_resources


def _migrate_false_crud(
    input_config: dict[str, Any],
    state: dict[str, Any],
    corrections: dict[str, object],
    changes: list[MigrationChange],
) -> None:
    false_crud = _mapping(corrections.get("false_crud"), "false CRUD")
    for raw_correction in false_crud.values():
        correction = _mapping(raw_correction, "false CRUD correction")
        _migrate_false_crud_correction(
            input_config,
            state,
            correction,
            changes,
        )


def _migrate_false_crud_correction(
    input_config: dict[str, Any],
    state: dict[str, Any],
    correction: dict[str, object],
    changes: list[MigrationChange],
) -> None:
    transform = _parse_false_crud_transform(correction)
    if transform.unsupported_files:
        if _entity_present(input_config, transform.legacy_entity):
            raise MigrationError(
                f"{transform.legacy_entity!r} requires manual remediation while the "
                "Files SDK remains unsupported."
            )
        return
    _validate_false_crud_state(
        state,
        transform.legacy_entity,
        transform.state_behavior,
    )
    for domain_name, domain in _domains(input_config).items():
        resources = _optional_mapping(domain.get("resources"), "resources")
        _migrate_false_crud_domain(
            resources,
            domain_name,
            transform,
            changes,
        )
    if transform.state_behavior == "remove_legacy_entity":
        _remove_false_crud_state(
            state,
            transform.legacy_entity,
            transform.canonical_entity,
            changes,
        )


def _parse_false_crud_transform(
    correction: dict[str, object],
) -> _FalseCrudTransform:
    replacement = _mapping(correction.get("replacement"), "replacement")
    migration = _mapping(correction.get("migration"), "false CRUD migration")
    return _FalseCrudTransform(
        legacy_entity=_string(correction.get("legacy_entity"), "legacy entity"),
        canonical_entity=_string(
            replacement.get("entity"),
            "replacement entity",
        ),
        operation_name=_string(
            replacement.get("operation"),
            "replacement operation",
        ),
        state_behavior=_string(
            migration.get("state_behavior"),
            "state behavior",
        ),
        unsupported_files=correction.get("status") == "unsupported_files",
        migration=migration,
    )


def _migrate_false_crud_domain(
    resources: dict[str, Any],
    domain_name: str,
    transform: _FalseCrudTransform,
    changes: list[MigrationChange],
) -> None:
    legacy_resources = _optional_mapping(
        resources.get(transform.legacy_entity),
        transform.legacy_entity,
    )
    for resource_name in list(legacy_resources):
        resource = _mapping(
            legacy_resources[resource_name],
            f"{transform.legacy_entity}.{resource_name}",
        )
        operation = _false_crud_operation(
            resource,
            transform.operation_name,
            transform.migration,
        )
        _replace_false_crud_resource(
            resources,
            transform,
            resource_name,
            resource,
            operation,
        )
        changes.append(
            MigrationChange(
                kind="false_crud",
                document="input",
                domain=domain_name,
                source=transform.legacy_entity,
                target=transform.canonical_entity,
                resource_name=resource_name,
            )
        )
    if transform.legacy_entity != transform.canonical_entity and not legacy_resources:
        resources.pop(transform.legacy_entity, None)


def _false_crud_operation(
    resource: dict[str, object],
    operation_name: str,
    migration: dict[str, object],
) -> dict[str, object]:
    accepted = set(
        _string_list(
            migration.get("adapter_parameters"),
            "adapter parameters",
        )
    )
    path_parameters = _string_list(
        migration.get("path_parameters"),
        "path parameters",
    )
    raw_params = resource.get("params", {})
    params = copy.deepcopy(_mapping(raw_params, "resource params"))
    ext_id = resource.get("extId") or resource.get("ext_id")
    missing_path_params = [
        parameter for parameter in path_parameters if parameter not in params
    ]
    if ext_id is not None and len(missing_path_params) == 1:
        params[missing_path_params[0]] = ext_id
    elif ext_id is not None and len(missing_path_params) > 1:
        raise MigrationError(
            "False CRUD resource has one extId but multiple unresolved path "
            f"parameters: {missing_path_params}"
        )
    unknown = sorted(set(params) - accepted)
    if unknown:
        raise MigrationError(
            f"False CRUD resource has unsupported parameters: {unknown}"
        )
    operation: dict[str, object] = {"type": operation_name}
    if params:
        operation["params"] = params
    if "body" in resource:
        operation["body"] = copy.deepcopy(resource["body"])
    return operation


def _replace_false_crud_resource(
    resources: dict[str, Any],
    transform: _FalseCrudTransform,
    resource_name: str,
    source: dict[str, object],
    operation: dict[str, object],
) -> None:
    canonical_resources = _optional_mapping(
        resources.get(transform.canonical_entity),
        transform.canonical_entity,
    )
    target = (
        {}
        if transform.legacy_entity == transform.canonical_entity
        else _optional_mapping(canonical_resources.get(resource_name), resource_name)
    )
    for metadata_key in ("rules", "depends_on"):
        if metadata_key in source:
            target[metadata_key] = copy.deepcopy(source[metadata_key])
    operations = _operation_list(target)
    operations.append(operation)
    target["operations"] = operations
    canonical_resources[resource_name] = target
    resources[transform.canonical_entity] = canonical_resources
    if transform.legacy_entity != transform.canonical_entity:
        legacy_resources = _optional_mapping(
            resources.get(transform.legacy_entity),
            transform.legacy_entity,
        )
        legacy_resources.pop(resource_name, None)


def _validate_false_crud_state(
    state: dict[str, Any],
    legacy_entity: str,
    state_behavior: str,
) -> None:
    if state_behavior != "manual_if_present":
        return
    for domain_name, domain in _domains(state).items():
        resources = _optional_mapping(domain.get("resources"), "state resources")
        if _optional_mapping(resources.get(legacy_entity), legacy_entity):
            raise MigrationError(
                f"State for {legacy_entity!r} in domain {domain_name!r} requires "
                "manual remediation; it may represent a real managed resource."
            )


def _remove_false_crud_state(
    state: dict[str, Any],
    legacy_entity: str,
    canonical_entity: str,
    changes: list[MigrationChange],
) -> None:
    for domain_name, domain in _domains(state).items():
        resources = _optional_mapping(domain.get("resources"), "state resources")
        if legacy_entity not in resources:
            continue
        resources.pop(legacy_entity)
        changes.append(
            MigrationChange(
                kind="false_crud_state_removal",
                document="state",
                domain=domain_name,
                source=legacy_entity,
                target=canonical_entity,
            )
        )


def _operation_list(resource: dict[str, object]) -> list[dict[str, object]]:
    raw_operations = resource.get("operations", [])
    if not isinstance(raw_operations, list):
        raise MigrationError("Resource operations must be a list")
    return [_mapping(operation, "resource operation") for operation in raw_operations]


def _remove_empty_resource(
    resources: dict[str, Any],
    resource_name: str,
    resource: dict[str, object],
) -> None:
    if not resource.get("operations"):
        resource.pop("operations", None)
    payload_keys = set(resource) - {"rules", "depends_on"}
    if not payload_keys:
        resources.pop(resource_name, None)


def _entity_present(document: dict[str, Any], entity: str) -> bool:
    return any(
        entity in _optional_mapping(domain.get("resources"), "resources")
        for domain in _domains(document).values()
    )


def _validate_document(
    document: dict[str, Any],
    label: str,
    *,
    require_domains: bool,
) -> None:
    domains = _domains(document)
    if require_domains and not domains:
        raise MigrationError(f"{label} must contain at least one domain")
    for domain_name, domain in domains.items():
        for section_name in ("resources", "data"):
            if section_name in domain:
                _mapping(
                    domain[section_name],
                    f"{label} domain {domain_name} {section_name}",
                )


def _domains(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_domains = document.get("domains", {})
    domains = _mapping(raw_domains, "domains")
    return {
        name: _mapping(domain, f"domain {name}") for name, domain in domains.items()
    }


def _load_correction_document() -> dict[str, object]:
    path = Path(__file__).parent / "entity_wrapper/registry_corrections.json"
    return _mapping(orjson.loads(path.read_bytes()), "registry corrections")


def _write_review_siblings(
    input_path: Path,
    state_path: Path,
    input_bytes: bytes,
    state_bytes: bytes,
) -> dict[str, str]:
    input_output = _migration_sibling(input_path)
    state_output = _migration_sibling(state_path)
    _atomic_write_bytes(input_output, input_bytes)
    _atomic_write_bytes(state_output, state_bytes)
    return {
        "migrated_input": str(input_output),
        "migrated_state": str(state_output),
    }


def _write_originals_transactionally(
    files: _MigrationFiles,
) -> dict[str, str]:
    from ztf.main import (
        _set_readonly,
        _set_writable,
        _StateFileLock,
    )

    input_backup = _backup_path(files.input_path)
    state_backup = _backup_path(files.state_path)
    if input_backup.exists() or state_backup.exists():
        raise MigrationError(
            "One-time migration backup already exists; preserve or remove it "
            "after reviewing the prior attempt."
        )
    with _StateFileLock(str(files.state_path)):
        _verify_unchanged(files.input_path, files.original_input)
        _verify_unchanged(files.state_path, files.original_state)
        _set_writable(str(files.state_path))
        shutil.copy2(files.input_path, input_backup)
        shutil.copy2(files.state_path, state_backup)
        try:
            _atomic_write_bytes(files.input_path, files.migrated_input)
            _atomic_write_bytes(files.state_path, files.migrated_state)
        except OSError as exc:
            _restore_originals(files, input_backup, state_backup)
            raise MigrationError(
                f"Migration write failed and originals were restored: {exc}"
            ) from exc
        finally:
            _set_readonly(str(files.state_path))
    return {
        "input_backup": str(input_backup),
        "state_backup": str(state_backup),
        "migrated_input": str(files.input_path),
        "migrated_state": str(files.state_path),
    }


def _restore_originals(
    files: _MigrationFiles,
    input_backup: Path,
    state_backup: Path,
) -> None:
    try:
        _atomic_write_bytes(files.input_path, files.original_input)
        _atomic_write_bytes(files.state_path, files.original_state)
    except OSError as exc:
        raise MigrationError(
            "Migration rollback failed. Restore the originals from "
            f"{input_backup} and {state_backup} before running ZTF."
        ) from exc


def _verify_unchanged(path: Path, expected: bytes) -> None:
    if path.read_bytes() != expected:
        raise MigrationError(f"{path} changed while migration was being prepared")


def _migration_sibling(path: Path) -> Path:
    return path.with_name(f"{path.stem}.entity-registry-migrated{path.suffix}")


def _backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.pre-entity-registry-migration.bak")


def _migration_report(
    files: _MigrationFiles,
    result: MigrationResult,
    write: bool,
    output_paths: dict[str, str],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "write" if write else "dry_run",
        "changed": result.changed,
        "change_count": len(result.changes),
        "changes": [asdict(change) for change in result.changes],
        "sources": {
            "input": {
                "path": str(files.input_path),
                "sha256": hashlib.sha256(files.original_input).hexdigest(),
            },
            "state": {
                "path": str(files.state_path),
                "sha256": hashlib.sha256(files.original_state).hexdigest(),
            },
        },
        "outputs": output_paths,
        "next_steps": (
            ["Run 'ztf refresh', review state, then run 'ztf plan'."]
            if write and result.changed
            else ["Review migrated sibling files, then rerun with --write."]
            if result.changed
            else ["No known legacy entity-registry forms were detected."]
        ),
    }


def _read_required_file(path: Path, label: str) -> bytes:
    if not path.is_file():
        raise MigrationError(f"{label} {path} does not exist or is not a file")
    return path.read_bytes()


def _load_yaml_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(data) or {}
    except yaml.YAMLError as exc:
        raise MigrationError(f"Cannot parse {label}: {exc}") from exc
    return _mapping(value, label)


def _yaml_bytes(value: dict[str, Any]) -> bytes:
    data = yaml.safe_dump(value, sort_keys=False).encode()
    loaded = _load_yaml_bytes(data, "serialized migration output")
    if loaded != value:
        raise MigrationError("Serialized migration output failed round-trip validation")
    return data


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MigrationError(f"{label} must be a string-keyed mapping")
    return value


def _optional_mapping(value: object, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    return _mapping(value, label)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationError(f"{label} must be a non-empty string")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise MigrationError(f"{label} must be a string list")
    return tuple(value)
