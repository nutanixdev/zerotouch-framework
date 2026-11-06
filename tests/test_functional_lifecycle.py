"""Functional lifecycle test: init -> plan -> apply -> refresh -> plan -> destroy.

Exercises all 11 gap fixes end-to-end using a mocked API layer
(storage_container resource from config/input.yml as the template).
"""

import os
from copy import deepcopy
from unittest.mock import MagicMock, patch

import yaml

import ztf.main as main_mod
from ztf.config.config_loader import load_config
from ztf.provider.provider import Provider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GLOBAL_CONFIG = {
    "config": {
        "port": 9440,
        "debug": False,
        "verify_ssl": True,
        "dry_run": False,
        "connect_timeout": 10,
        "read_timeout": 60,
    }
}

INPUT_CONFIG = {
    "domains": {
        "lab1": {
            "host": "10.10.0.108",
            "username": "admin",
            "password": "pass",
            "data": {
                "cluster": {
                    "grove_cluster": {
                        "filter": "name eq 'grove1-3'",
                    }
                }
            },
            "resources": {
                "storage_container": {
                    "sc1": {
                        "X_Cluster_Id": "{cluster.grove_cluster.ext_id}",
                        "body": {
                            "name": "example-storage-container",
                            "logical_explicit_reserved_capacity_bytes": 536870912,
                            "logical_advertised_capacity_bytes": 1073741824,
                            "replication_factor": 2,
                            "is_compression_enabled": True,
                            "compression_delay_secs": 600,
                            "erasure_code": "OFF",
                        },
                    }
                }
            },
        }
    }
}


def _make_provider_with_mocks(
    config_data: dict, state: dict
) -> tuple[Provider, MagicMock]:
    """Create a Provider with mocked DomainEntityHandler.

    ``strip_readonly_fields`` defaults to a passthrough so callers'
    ``sanitize_entity_data`` bodies flow through unchanged unless a test
    explicitly overrides it to assert on readOnly-stripping behavior.
    """
    config = load_config(deepcopy(config_data))
    with patch("ztf.provider.provider.DomainEntityHandler", autospec=True) as mock_cls:
        handler = mock_cls.return_value
        handler.entity_metadata_map = {
            "storage_container": {
                "update_supported": True,
                "sdk_name": "ntnx_clustermgmt_py_client",
                "filter_format": "name eq '{name}'",
            },
            "prism_task": {
                "sdk_name": "ntnx_prism_py_client",
            },
        }
        handler.strip_readonly_fields.side_effect = (
            lambda _entity, body, operation="create": body
        )
        provider = Provider(deepcopy(GLOBAL_CONFIG), config, deepcopy(state))
        return provider, handler


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end lifecycle: init -> plan -> apply -> refresh -> plan -> destroy."""

    def test_init_creates_empty_state(self, tmp_path, monkeypatch):
        """Step 1: init creates an empty locked state file."""
        state_file = tmp_path / "state.yml"
        monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)

        main_mod._write_state(str(state_file), {"domains": {}})
        assert state_file.exists()
        with open(state_file) as fh:
            data = yaml.safe_load(fh)
        assert data == {"domains": {}}

    def test_plan_shows_create(self):
        """Step 2: plan on empty state shows CREATE for sc1."""
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, {"domains": {}})
        plan = provider.plan()
        creates = plan.get("create", {}).get("lab1", {})
        sc_creates = creates.get("storage_container", [])
        assert len(sc_creates) == 1
        assert sc_creates[0]["resource_name"] == "sc1"

    def test_apply_creates_resource(self, tmp_path, monkeypatch):
        """Step 3: apply creates the resource and writes state incrementally."""
        monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
        state_file = tmp_path / "state.yml"
        with open(state_file, "w") as fh:
            yaml.safe_dump({"domains": {}}, fh)

        # Use a simplified config without data-source interpolation
        simple_config = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "username": "admin",
                    "password": "pass",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "body": {
                                    "name": "example-storage-container",
                                    "replication_factor": 2,
                                    "is_compression_enabled": True,
                                },
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(simple_config, {"domains": {}})
        handler.create.return_value = "sc-ext-123"

        state_snapshots = []

        def on_state_change(state: dict) -> None:
            state_snapshots.append(deepcopy(state))

        new_state = provider.run(on_state_change=on_state_change)

        # Gap 4: incremental state callback was invoked
        assert len(state_snapshots) >= 1

        # Verify resource in state
        lab1 = new_state.get("domains", {}).get("lab1", {})
        sc_res = lab1.get("resources", {}).get("storage_container", {})
        assert "sc1" in sc_res
        assert sc_res["sc1"]["extId"] == "sc-ext-123"

        # Gap 11: write state with backup
        main_mod._write_state(str(state_file), new_state)
        assert state_file.exists()
        # Write again to create backup
        main_mod._write_state(str(state_file), new_state)
        backup = tmp_path / "state.yml.bak"
        assert backup.exists()

    def test_refresh_updates_full_body(self):
        """Step 4: refresh stores full API body (Gap 8) and keeps resource on error (Gap 9)."""
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": {
                                    "name": "example-storage-container",
                                    "replication_factor": 2,
                                },
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, prev_state)

        # API returns full body with new fields
        handler.get_entity_by_ext_id.return_value = MagicMock()
        handler.sanitize_entity_data.return_value = {
            "name": "example-storage-container",
            "replication_factor": 2,
            "is_compression_enabled": True,
            "api_added_field": "surprise",
        }

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        body = lab1["resources"]["storage_container"]["sc1"]["body"]

        # Gap 8: full body stored, including api_added_field
        assert body["api_added_field"] == "surprise"
        assert body["is_compression_enabled"] is True

    def test_refresh_keeps_previous_on_error(self):
        """Gap 9: refresh keeps previous state entry on API error."""
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": {"name": "example-storage-container"},
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, prev_state)
        handler.get_entity_by_ext_id.side_effect = Exception("API timeout")

        refreshed = provider.refresh_state()
        lab1 = refreshed.get("domains", {}).get("lab1", {})
        sc1 = lab1["resources"]["storage_container"]["sc1"]
        assert sc1["extId"] == "sc-ext-123"
        assert sc1["body"]["name"] == "example-storage-container"

    def test_plan_no_change_after_refresh(self):
        """Step 5: plan after refresh with matching state shows no changes."""
        matching_body = {
            "name": "example-storage-container",
            "logical_explicit_reserved_capacity_bytes": 536870912,
            "logical_advertised_capacity_bytes": 1073741824,
            "replication_factor": 2,
            "is_compression_enabled": True,
            "compression_delay_secs": 600,
            "erasure_code": "OFF",
        }
        matching_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": matching_body,
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, matching_state)
        plan = provider.plan()
        creates = plan.get("create", {})
        updates = plan.get("update", {})
        deletes = plan.get("delete", {})
        assert not creates
        assert not updates
        assert not deletes

    def test_plan_field_level_diff_on_change(self):
        """Gap 3: plan shows field-level diff when body differs."""
        changed_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": {
                                    "name": "example-storage-container",
                                    "logical_explicit_reserved_capacity_bytes": 999999,
                                    "logical_advertised_capacity_bytes": 1073741824,
                                    "replication_factor": 2,
                                    "is_compression_enabled": True,
                                    "compression_delay_secs": 600,
                                    "erasure_code": "OFF",
                                },
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, changed_state)
        plan = provider.plan()
        updates = plan.get("update", {}).get("lab1", {}).get("storage_container", [])
        assert len(updates) == 1
        diff = updates[0].get("diff_fields", {})
        assert "changed" in diff
        assert "logical_explicit_reserved_capacity_bytes" in diff["changed"]

    def test_destroy_removes_all(self):
        """Step 6: destroy removes all resources."""
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": {"name": "example-storage-container"},
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, prev_state)
        handler.delete.return_value = None

        callback_states = []

        def on_change(state: dict) -> None:
            callback_states.append(deepcopy(state))

        new_state = provider.destroy(on_state_change=on_change)

        # Gap 4: callback invoked
        assert len(callback_states) >= 1

        # All resources deleted
        domains = new_state.get("domains", {})
        if "lab1" in domains:
            resources = domains["lab1"].get("resources", {})
            assert not resources

    def test_domain_failure_preserves_state(self):
        """Gap 5: domain-level failure returns previous state, not empty."""
        prev_state = {
            "domains": {
                "lab1": {
                    "host": "10.10.0.108",
                    "resources": {
                        "storage_container": {
                            "sc1": {
                                "extId": "sc-ext-123",
                                "body": {"name": "example-storage-container"},
                            }
                        }
                    },
                }
            }
        }
        provider, handler = _make_provider_with_mocks(INPUT_CONFIG, prev_state)

        with patch.object(
            provider,
            "_fetch_data_sources",
            side_effect=Exception("data source failure"),
        ):
            results, domain_name = provider._run_domain_for_upsert("lab1")
            assert domain_name == "lab1"
            assert "storage_container" in results
            assert "sc1" in results["storage_container"]
            assert results["storage_container"]["sc1"]["extId"] == "sc-ext-123"
