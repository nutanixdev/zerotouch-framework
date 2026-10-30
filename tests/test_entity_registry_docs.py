"""Documentation accountability for reviewed registry corrections."""

from pathlib import Path

import orjson


def test_registry_migration_document_covers_every_correction() -> None:
    """Each generated correction names its source and replacement in docs."""
    project_root = Path(__file__).resolve().parents[1]
    corrections = orjson.loads(
        (project_root / "ztf/entity_wrapper/registry_corrections.json").read_bytes()
    )
    documentation = (project_root / "docs/entity-registry-migration.md").read_text(
        encoding="utf-8"
    )

    for alias, correction in corrections["entity_aliases"].items():
        assert f"`{alias}`" in documentation
        assert f"`{correction['canonical_name']}`" in documentation
    for correction in corrections["operation_owner_changes"].values():
        assert f"`{correction['legacy_owner']}." in documentation
        assert f"`{correction['canonical_owner']}.{correction['operation']}`" in (
            documentation
        )
    for correction in corrections["false_crud"].values():
        replacement = correction["replacement"]
        assert f"`{correction['legacy_entity']}." in documentation
        assert f"`{replacement['entity']}.{replacement['operation']}`" in (
            documentation
        )
    assert "certifi" in documentation
    assert "ztf migrate entity-registry" in documentation
