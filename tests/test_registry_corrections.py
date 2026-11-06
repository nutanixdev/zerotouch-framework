"""Tests for runtime legacy-registry correction lookup."""

import pytest

from ztf.entity_wrapper.registry_corrections import (
    RegistryCorrections,
    load_registry_corrections,
)


def test_moved_operation_matches_public_and_legacy_names() -> None:
    """Moved owner lookup recognizes public and released SDK spellings."""
    corrections = load_registry_corrections()

    public = corrections.moved_operation("bridge", "migrate")
    legacy = corrections.moved_operation("bridge", "migrate_bridge")

    assert public is not None
    assert legacy == public
    assert public.canonical_owner == "virtual_switch"
    assert public.operation == "migrate"
    assert public.behavior == "warn_and_reject"


def test_false_crud_lookup_returns_action_replacement() -> None:
    """False lifecycle syntax resolves to an actionable operation replacement."""
    corrections = load_registry_corrections()

    correction = corrections.false_crud("user_state", "update")

    assert correction is not None
    assert correction.canonical_entity == "user"
    assert correction.operation == "change_state"
    assert correction.behavior == "warn_and_reject"


def test_unknown_legacy_binding_has_no_correction() -> None:
    """Unrelated entities and methods do not trigger compatibility handling."""
    corrections = load_registry_corrections()

    assert corrections.moved_operation("user", "change_state") is None
    assert corrections.false_crud("user", "update") is None


def test_removed_entity_lookup_returns_public_api_tombstone() -> None:
    """Removed public entities retain warning-only compatibility metadata."""
    corrections = RegistryCorrections(
        {
            "operation_owner_changes": {},
            "false_crud": {},
            "removed_entities": {
                "consistency_group": {
                    "namespace": "dataprotection",
                    "behavior": "warn_and_reject",
                    "reason": "internal_only",
                    "replacement": None,
                },
                "legacy_group": {
                    "namespace": "dataprotection",
                    "behavior": "warn_and_reject",
                    "reason": "renamed",
                    "replacement": "replacement_group",
                },
            },
        }
    )

    removal = corrections.removed_entity("consistency_group")

    assert removal is not None
    assert removal.namespace == "dataprotection"
    assert removal.behavior == "warn_and_reject"
    assert removal.reason == "internal_only"
    assert removal.replacement is None
    assert corrections.removed_entity("legacy_group").replacement == (
        "replacement_group"
    )
    assert corrections.removed_entity("protection_policy") is None


@pytest.mark.parametrize(
    ("tombstone", "message"),
    [
        (
            {
                "namespace": "dataprotection",
                "behavior": "warn_and_resolve",
                "reason": "internal_only",
                "replacement": None,
            },
            "Unsupported removed entity behavior",
        ),
        (
            {
                "namespace": "dataprotection",
                "behavior": "warn_and_reject",
                "reason": "internal_only",
                "replacement": 1,
            },
            "replacement must be a non-empty string",
        ),
    ],
)
def test_removed_entity_rejects_invalid_tombstones(
    tombstone: dict[str, object],
    message: str,
) -> None:
    """Malformed removal behavior cannot enter the runtime lookup."""
    with pytest.raises(ValueError, match=message):
        RegistryCorrections(
            {
                "operation_owner_changes": {},
                "false_crud": {},
                "removed_entities": {"consistency_group": tombstone},
            }
        )
