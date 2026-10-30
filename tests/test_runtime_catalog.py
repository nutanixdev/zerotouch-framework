"""Tests for generated runtime entity-catalog lookup."""

from ztf.entity_wrapper.runtime_catalog import load_runtime_catalog


def test_catalog_resolves_entity_aliases() -> None:
    """Released names resolve to one canonical entity identity."""
    catalog = load_runtime_catalog()

    assert catalog.resolve_entity("aiops_sources_v4") == "aiops_stats_source"
    assert catalog.resolve_entity("category_mapping") == (
        "directory_server_category_mapping"
    )
    assert catalog.resolve_entity("user") == "user"
    assert catalog.resolve_entity("unknown") is None


def test_catalog_resolves_public_and_sdk_operation_names() -> None:
    """Public operation keys and compatibility aliases share one adapter."""
    catalog = load_runtime_catalog()

    public = catalog.resolve_operation("virtual_switch", "migrate")
    compatibility = catalog.resolve_operation(
        "virtual_switch",
        "migrate_bridge",
    )

    assert public is not None
    assert compatibility == public
    assert public.operation_id == "migrateBridge"
    assert public.module == "ntnx_networking_py_client.api.bridges_api"
    assert public.api_class == "BridgesApi"
    assert public.method == "migrate_bridge"


def test_catalog_resolves_exact_lifecycle_operation() -> None:
    """Lifecycle lookup retains exact operation IDs and per-method adapters."""
    catalog = load_runtime_catalog()

    operation = catalog.resolve_lifecycle(
        "ds_category_mapping",
        "get",
    )

    assert operation is not None
    assert operation.canonical_entity == "directory_server_category_mapping"
    assert operation.operation_id == "getDsCategoryMappingById"
    assert operation.method == "get_ds_category_mapping_by_id"
