"""Tests for the optional one-time entity-registry migration."""

from copy import deepcopy

import orjson
import pytest
import yaml
from click.testing import CliRunner

import ztf.entity_registry_migration as migration_module
from ztf.entity_registry_migration import (
    MigrationError,
    migrate_entity_registry_documents,
)
from ztf.main import cli


def test_migration_renames_and_merges_stateful_entity_aliases() -> None:
    """Released resource headings merge under the reviewed canonical entity."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "category_mapping": {"collection": {"body": {"name": "a"}}},
                    "ds_category_mapping": {"item": {"body": {"name": "b"}}},
                },
                "data": {"aiops_sources_v4": {"source": {"filter": "name eq 'stats'"}}},
            }
        },
        "outputs": {
            "source_id": {"value": "{data.lab.aiops_sources_v4.source.data.0.extId}"}
        },
    }
    state = {
        "domains": {
            "lab": {
                "resources": {
                    "category_mapping": {"collection": {"extId": "one"}},
                    "ds_category_mapping": {"item": {"extId": "two"}},
                }
            }
        }
    }

    result = migrate_entity_registry_documents(config, state)

    resources = result.input_config["domains"]["lab"]["resources"]
    assert sorted(resources["directory_server_category_mapping"]) == [
        "collection",
        "item",
    ]
    assert "category_mapping" not in resources
    assert "ds_category_mapping" not in resources
    assert "aiops_stats_source" in result.input_config["domains"]["lab"]["data"]
    assert result.input_config["outputs"]["source_id"]["value"] == (
        "{data.lab.aiops_stats_source.source.data.0.extId}"
    )
    state_resources = result.state["domains"]["lab"]["resources"]
    assert sorted(state_resources["directory_server_category_mapping"]) == [
        "collection",
        "item",
    ]
    assert result.changed


def test_migration_reparents_stateless_operation_without_state_change() -> None:
    """Only configuration changes when an operation owner is corrected."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "bridge": {
                        "migrate_existing": {
                            "operations": [
                                {
                                    "type": "migrate_bridge",
                                    "params": {"extId": "bridge-id"},
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    state = {"domains": {"lab": {"resources": {"bridge": {"kept": {}}}}}}
    original_state = deepcopy(state)

    result = migrate_entity_registry_documents(config, state)

    resources = result.input_config["domains"]["lab"]["resources"]
    operation = resources["virtual_switch"]["migrate_existing"]["operations"][0]
    assert operation["type"] == "migrate"
    assert "bridge" not in resources
    assert result.state == original_state


def test_migration_converts_false_crud_and_removes_synthetic_state() -> None:
    """Reviewed action-as-update syntax becomes an operation-only resource."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "user_state": {
                        "activate": {
                            "extId": "user-id",
                            "body": {"state": "ACTIVE"},
                        }
                    }
                }
            }
        }
    }
    state = {
        "domains": {
            "lab": {
                "resources": {
                    "user_state": {
                        "activate": {
                            "extId": "user-id",
                            "body": {"state": "ACTIVE"},
                        }
                    }
                }
            }
        }
    }

    result = migrate_entity_registry_documents(config, state)

    resources = result.input_config["domains"]["lab"]["resources"]
    operation = resources["user"]["activate"]["operations"][0]
    assert operation == {
        "type": "change_state",
        "params": {"extId": "user-id"},
        "body": {"state": "ACTIVE"},
    }
    assert "user_state" not in result.state["domains"]["lab"]["resources"]


def test_migration_stops_on_ambiguous_same_entity_false_crud_state() -> None:
    """State shared with a real resource requires manual remediation."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "entity_sync_policy": {
                        "sync": {
                            "extId": "policy-id",
                            "body": {"entityExtIds": ["entity-id"]},
                        }
                    }
                }
            }
        }
    }
    state = {
        "domains": {
            "lab": {
                "resources": {"entity_sync_policy": {"sync": {"extId": "policy-id"}}}
            }
        }
    }

    with pytest.raises(MigrationError, match="manual remediation"):
        migrate_entity_registry_documents(config, state)


def test_migration_stops_on_conflicting_resource_merge() -> None:
    """No transform overwrites two unequal resources with the same name."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "category_mapping": {"same": {"body": {"name": "old"}}},
                    "directory_server_category_mapping": {
                        "same": {"body": {"name": "new"}}
                    },
                }
            }
        }
    }

    with pytest.raises(MigrationError, match="same"):
        migrate_entity_registry_documents(config, {"domains": {}})


def test_migration_is_idempotent() -> None:
    """The fixed correction set applies at most once to a document pair."""
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "bridge": {"move": {"operations": [{"type": "migrate_bridge"}]}}
                }
            }
        }
    }
    state = {"domains": {}}

    first = migrate_entity_registry_documents(config, state)
    second = migrate_entity_registry_documents(first.input_config, first.state)

    assert first.changed
    assert not second.changed
    assert second.input_config == first.input_config
    assert second.state == first.state


def test_migration_cli_dry_run_writes_review_siblings(tmp_path) -> None:
    """Default CLI mode leaves originals untouched and writes review files."""
    input_path, state_path = _write_alias_fixture(tmp_path)
    original_input = input_path.read_bytes()
    original_state = state_path.read_bytes()

    result = CliRunner().invoke(
        cli,
        [
            "migrate",
            "entity-registry",
            "--input",
            str(input_path),
            "--state",
            str(state_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert input_path.read_bytes() == original_input
    assert state_path.read_bytes() == original_state
    migrated_input = tmp_path / "input.entity-registry-migrated.yml"
    migrated_state = tmp_path / "state.entity-registry-migrated.yml"
    assert migrated_input.is_file()
    assert migrated_state.is_file()
    report = orjson.loads(
        (tmp_path / "entity-registry-migration-report.json").read_bytes()
    )
    assert report["mode"] == "dry_run"
    assert report["changed"] is True


def test_migration_cli_write_is_transactional_and_creates_backups(
    tmp_path,
) -> None:
    """Write mode replaces both documents and retains one-time backups."""
    input_path, state_path = _write_alias_fixture(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            "migrate",
            "entity-registry",
            "--input",
            str(input_path),
            "--state",
            str(state_path),
            "--write",
        ],
    )

    assert result.exit_code == 0, result.output
    migrated_input = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    migrated_state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    assert (
        "directory_server_category_mapping"
        in migrated_input["domains"]["lab"]["resources"]
    )
    assert (
        "directory_server_category_mapping"
        in migrated_state["domains"]["lab"]["resources"]
    )
    assert (tmp_path / "input.yml.pre-entity-registry-migration.bak").is_file()
    assert (tmp_path / "state.yml.pre-entity-registry-migration.bak").is_file()
    assert "ztf refresh" in result.output
    assert "ztf plan" in result.output


def test_transactional_write_restores_both_files_on_failure(
    tmp_path,
    monkeypatch,
) -> None:
    """A second-file write failure rolls the first file back."""
    input_path, state_path = _write_alias_fixture(tmp_path)
    original_input = input_path.read_bytes()
    original_state = state_path.read_bytes()
    original_atomic_write = migration_module._atomic_write_bytes
    failed = False

    def fail_state_once(path, data):
        nonlocal failed
        if path == state_path and not failed:
            failed = True
            raise OSError("simulated state write failure")
        original_atomic_write(path, data)

    monkeypatch.setattr(
        migration_module,
        "_atomic_write_bytes",
        fail_state_once,
    )

    with pytest.raises(MigrationError, match="originals were restored"):
        migration_module.run_entity_registry_migration(
            input_path,
            state_path,
            write=True,
        )

    assert input_path.read_bytes() == original_input
    assert state_path.read_bytes() == original_state


def _write_alias_fixture(tmp_path):
    config = {
        "domains": {
            "lab": {
                "resources": {
                    "category_mapping": {"mapping": {"body": {"name": "mapping"}}}
                }
            }
        }
    }
    state = {
        "domains": {
            "lab": {
                "resources": {"category_mapping": {"mapping": {"extId": "mapping-id"}}}
            }
        }
    }
    input_path = tmp_path / "input.yml"
    state_path = tmp_path / "state.yml"
    input_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    state_path.write_text(yaml.safe_dump(state), encoding="utf-8")
    return input_path, state_path
