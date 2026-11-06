"""Tests for ``entity_map.get_operation_schema`` utility."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ztf.entity_wrapper.entity_map import _snake_to_camel, get_operation_schema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FAKE_COMPAT_MAP: dict[str, Any] = {
    "clustermgmt": {
        "createClusterProfile": {
            "schema": {
                "request": {
                    "name": {
                        "readOnly": False,
                        "versions": [4.0, 4.1],
                    }
                }
            },
        },
        "applyClusterProfile": {
            "schema": {},
        },
        "getSSLCertificate": {
            "schema": {"request": {"exact": True}},
        },
    }
}


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Reset the module-level cache before each test."""
    import ztf.entity_wrapper.entity_map as mod

    mod._compat_cache = None


@pytest.fixture()
def _patch_compat_map(tmp_path: Path) -> Path:
    """Write a fake compat map and patch the path constant."""
    out = tmp_path / "compat.json"
    with open(out, "w") as fh:
        json.dump(_FAKE_COMPAT_MAP, fh)

    import ztf.entity_wrapper.entity_map as mod

    original = mod._COMPAT_MAP_PATH
    mod._COMPAT_MAP_PATH = out
    yield out
    mod._COMPAT_MAP_PATH = original


# ---------------------------------------------------------------------------
# Tests: _snake_to_camel
# ---------------------------------------------------------------------------


class TestSnakeToCamel:
    def test_simple(self) -> None:
        assert _snake_to_camel("create_cluster_profile") == "createClusterProfile"

    def test_single_word(self) -> None:
        assert _snake_to_camel("list") == "list"

    def test_multiple_underscores(self) -> None:
        assert _snake_to_camel("get_vm_by_id") == "getVmById"


# ---------------------------------------------------------------------------
# Tests: get_operation_schema
# ---------------------------------------------------------------------------


class TestGetOperationSchema:
    def test_create_method(self, _patch_compat_map: Path) -> None:
        """Lookup by standard 'create' method key."""
        result = get_operation_schema("cluster_profile", "create")
        assert result is not None
        assert "schema" in result
        req = result["schema"]["request"]
        assert "name" in req
        assert 4.0 in req["name"]["versions"]

    def test_custom_operation(self, _patch_compat_map: Path) -> None:
        """Lookup by custom operation name from the 'operations' list."""
        result = get_operation_schema(
            "cluster_profile",
            "apply_cluster_profile",
        )
        assert result is not None
        assert "schema" in result

    def test_exact_catalog_operation_id(self, _patch_compat_map: Path) -> None:
        """Catalog identity preserves acronym casing absent from SDK methods."""
        result = get_operation_schema("cluster_ssl_certificate", "get")

        assert result == {"schema": {"request": {"exact": True}}}

    def test_unknown_entity(self, _patch_compat_map: Path) -> None:
        """Unknown entity should return None."""
        assert get_operation_schema("nonexistent_entity") is None

    def test_unknown_method(self, _patch_compat_map: Path) -> None:
        """Unknown method key should return None."""
        assert get_operation_schema("cluster_profile", "archive") is None

    def test_missing_compat_map(self, tmp_path: Path) -> None:
        """When the compat map file doesn't exist, return None."""
        import ztf.entity_wrapper.entity_map as mod

        mod._COMPAT_MAP_PATH = tmp_path / "nonexistent.json"
        assert get_operation_schema("cluster_profile", "create") is None


# ---------------------------------------------------------------------------
# Cache hit / ImportError fallback / no-operations entity
# ---------------------------------------------------------------------------


class TestLoadCompatMapCache:
    def test_cache_hit(self, _patch_compat_map: Path) -> None:
        """Second call returns cached dict without re-reading file."""
        import ztf.entity_wrapper.entity_map as mod

        first = mod._load_compat_map()
        assert "clustermgmt" in first
        second = mod._load_compat_map()
        assert first is second

    def test_import_error_fallback(self, _patch_compat_map: Path) -> None:
        """When orjson import fails, json fallback is used."""
        import ztf.entity_wrapper.entity_map as mod

        mod._compat_cache = None
        with (
            patch.dict("sys.modules", {"orjson": None}),
            patch("builtins.__import__", side_effect=_import_no_orjson),
        ):
            result = mod._load_compat_map()
        assert "clustermgmt" in result


class TestGetOperationSchemaEdge:
    def test_entity_no_operations_key(self, _patch_compat_map: Path) -> None:
        """Entity exists but has no 'operations' list -- custom op returns None."""
        import ztf.entity_wrapper.entity_map as mod

        # Temporarily add a test entity with no operations key
        mod.entity_map["_test_entity"] = {
            "namespace": "clustermgmt",
            "create_method_name": "create_cluster_profile",
        }
        result = get_operation_schema("_test_entity", "custom_op")
        assert result is None
        del mod.entity_map["_test_entity"]


def _import_no_orjson(name, *args, **kwargs):
    """Import hook that blocks orjson."""
    if name == "orjson":
        raise ImportError("no orjson")
    return original_import(name, *args, **kwargs)


import builtins  # noqa: E402

original_import = builtins.__import__
