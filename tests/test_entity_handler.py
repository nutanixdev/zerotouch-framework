import logging
from unittest.mock import MagicMock, patch

import pytest

from ztf.entity_wrapper.entity_handler import (
    DomainEntityHandler,
    _default_method_name,
)
from ztf.entity_wrapper.runtime_catalog import RuntimeOperation


@pytest.fixture
def entity_map_patch(monkeypatch):
    # Patch the entity_map to a minimal valid structure for testing
    monkeypatch.setattr(
        "ztf.entity_wrapper.entity_handler.entity_map",
        {
            "entityA": {
                "sdk_name": "sdk_mod",
                "model_class_path": "ModelA",
                "api_class_path": "api_a",
                "create_method_name": "create_entityA",
                "get_method_name": "get_entityA_by_id",
                "update_method_name": "update_entityA_by_id",
                "delete_method_name": "delete_entityA_by_id",
                "list_method_name": "list_entityAs",
                "operations": ["do_something"],
                "filter_format": "name eq '{name}'",
                "update_supported": "True",
                "namespace": "test",
                "etag_required": {"update": False, "delete": False},
                "method_params": {
                    "create": ["body"],
                    "get": ["extId"],
                    "update": ["extId", "body"],
                    "delete": ["extId"],
                },
            },
            "entityB": {
                "sdk_name": "sdk_mod",
                "model_class_path": "ModelB",
                "api_class_name": "ApiB",
                "create_method_name": "create_entityB",
                "get_method_name": "get_entityB_by_id",
                "update_method_name": "update_entityB_by_id",
                "delete_method_name": "delete_entityB_by_id",
                "list_method_name": "list_entityBs",
                "operations": [],
                "filter_format": "name eq '{name}'",
                "update_supported": "True",
                "namespace": "test",
                "etag_required": {"update": False, "delete": False},
                "method_params": {
                    "create": ["body"],
                    "get": ["extId"],
                    "update": ["extId", "body"],
                    "delete": ["extId"],
                },
            },
            "task": {
                "api_class_path": "tasks_api",
                "api_instance": None,
                "sdk_name": "ntnx_prism_py_client",
                "model_class_path": "prism.v4.config.Task",
                "filter_format": "ext_id eq '{ext_id}'",
            },
            "prism_task": {
                "sdk_name": "ntnx_prism_py_client",
                "api_class_path": "tasks_api",
                "api_class_name": "TasksApi",
            },
            "entityC": {
                "sdk_name": "sdk_mod",
                "model_class_path": "ModelC",
                "api_class_path": "api_c",
                "create_method_name": "create_entityC",
                "get_method_name": "get_entityC_by_id",
                "update_method_name": "update_entityC_by_id",
                "delete_method_name": "delete_entityC_by_id",
                "list_method_name": "list_entityCs",
                "operations": [],
                "filter_format": "name eq '{name}'",
                "update_supported": "True",
                "namespace": "test",
                "etag_required": {"update": False, "delete": False},
                "method_params": {
                    "create": ["name", "isCertAuthEnabled", "dirSvcExtID"],
                    "get": ["extId"],
                    "update": ["extId", "name", "isCertAuthEnabled"],
                    "delete": ["extId"],
                },
            },
        },
    )


@pytest.fixture
def global_config():
    return {"config": {"host": "1.2.3.4", "username": "admin", "password": "pass"}}


@pytest.fixture
def handler(entity_map_patch, global_config):
    # Patch importlib to avoid real imports
    with patch("importlib.import_module") as import_mod:
        sdk_mod = MagicMock()
        sdk_mod.Configuration.return_value = MagicMock()
        sdk_mod.api_client.ApiClient.return_value = MagicMock()
        import_mod.return_value = sdk_mod
        return DomainEntityHandler({"entityA", "entityB", "entityC"}, global_config)


def test_initialize_entities_and_config(handler):
    assert "entityA" in handler.entity_metadata_map
    assert "entityB" in handler.entity_metadata_map
    assert isinstance(handler.sdk_config_map, dict)
    assert isinstance(handler.sdk_api_client_map, dict)


def test_initialize_entities_warns_for_deprecated_alias(
    monkeypatch,
    global_config,
):
    """Released entity aliases remain usable but emit one actionable warning."""
    logger = MagicMock()
    monkeypatch.setattr(
        "ztf.entity_wrapper.entity_handler.get_logger",
        lambda *args, **kwargs: logger,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_config",
        lambda *args: None,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_client",
        lambda *args: None,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_entity_crud_mapping",
        lambda *args: None,
    )
    metadata = {
        "aiops_sources_v4": {"sdk_name": "ntnx_aiops_py_client"},
        "prism_task": {"sdk_name": "ntnx_prism_py_client"},
    }

    DomainEntityHandler(
        {"aiops_sources_v4"},
        global_config,
        entity_metadata_map=metadata,
    )

    logger.warning.assert_any_call(
        "Entity %r is deprecated; use %r. The alias remains supported "
        "for this compatibility release.",
        "aiops_sources_v4",
        "aiops_stats_source",
    )


def test_initialize_entities_warns_and_rejects_removed_public_entity(
    monkeypatch,
    global_config,
):
    """A tombstoned entity fails before any internal SDK import or lookup."""
    logger = MagicMock()
    corrections = MagicMock()
    removal = MagicMock(
        namespace="dataprotection",
        behavior="warn_and_reject",
        reason="internal_only",
        replacement=None,
    )
    corrections.removed_entity.side_effect = lambda entity: (
        removal if entity == "consistency_group" else None
    )
    initialize_config = MagicMock()
    initialize_client = MagicMock()
    initialize_mapping = MagicMock()
    monkeypatch.setattr(
        "ztf.entity_wrapper.entity_handler.get_logger",
        lambda *args, **kwargs: logger,
    )
    monkeypatch.setattr(
        "ztf.entity_wrapper.entity_handler.load_registry_corrections",
        lambda: corrections,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_config",
        initialize_config,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_client",
        initialize_client,
    )
    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_entity_crud_mapping",
        initialize_mapping,
    )

    with pytest.raises(ValueError, match="removed from the public"):
        DomainEntityHandler(
            {"consistency_group"},
            global_config,
            entity_metadata_map={
                "prism_task": {"sdk_name": "ntnx_prism_py_client"},
            },
        )

    assert "remain on the prior ZTF release" in logger.warning.call_args.args[0]
    assert all(
        call.args[0] != "consistency_group" for call in initialize_config.call_args_list
    )
    assert all(
        call.args[0] != "consistency_group" for call in initialize_client.call_args_list
    )
    assert all(
        call.args[0] != "consistency_group"
        for call in initialize_mapping.call_args_list
    )


def test_get_class_from_path(monkeypatch):
    class Dummy:
        pass

    monkeypatch.setattr(
        "importlib.import_module", lambda path: type("Mod", (), {"Dummy": Dummy})
    )
    assert DomainEntityHandler._get_class_from_path("dummy_mod", "Dummy") == Dummy


def test_create_success(handler, monkeypatch):
    handler.entity_metadata_map["entityA"]["filter_format"] = "name eq '{name}'"
    handler.get_entity_by_identifier = MagicMock(return_value=(None, None))
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    response = MagicMock()
    response.data.ext_id = "extid123"
    api_instance.create_entityA.return_value = response
    ext_id = handler.create("entityA", {"body": {"name": "foo"}})
    assert ext_id == "extid123"


def test_create_no_data_attr(handler, monkeypatch):
    handler.entity_metadata_map["entityA"]["filter_format"] = "name eq '{name}'"
    handler.get_entity_by_identifier = MagicMock(return_value=(None, None))
    api_instance = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    # Simulate a response with no .data attribute
    response = MagicMock()
    del response.data
    api_instance.create_entityA.return_value = response
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})


def test_create_no_extid(handler, monkeypatch):
    handler.entity_metadata_map["entityA"]["filter_format"] = "name eq '{name}'"
    handler.get_entity_by_identifier = MagicMock(return_value=(None, None))
    api_instance = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    # spec=[] prevents MagicMock from auto-creating attributes
    response = MagicMock()
    response.data = MagicMock(spec=[])
    response.data.ext_id = None
    response.data._object_type = None
    api_instance.create_entityA.return_value = response
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})


def test_create_existing(handler):
    handler.entity_metadata_map["entityA"]["filter_format"] = "name eq '{name}'"
    handler.get_entity_by_identifier = MagicMock(
        return_value=(MagicMock(ext_id="abc123"), None)
    )
    extid = handler.create("entityA", {"body": {"name": "foo"}})
    assert extid == "abc123"


def test_create_missing_body(handler):
    with pytest.raises(ValueError):
        handler.create("entityA", {})


def test_create_unsupported_entity(handler):
    with pytest.raises(ValueError):
        handler.create("not_supported", {"body": {}})


def test_create_execute_method_error(handler):
    handler.entity_metadata_map["entityA"]["filter_format"] = None
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    handler._execute_method_with_task_monitor = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})


def test_update_success(handler):
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    api_instance.update_entityA_by_id.return_value = MagicMock(
        data=MagicMock(ext_id="abc")
    )
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"data": {}}
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._get_tag = MagicMock(return_value="etag")
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")
    extid = handler.update("entityA", {"body": {"name": "foo"}, "ext_id": "abc"})
    assert extid == "abc"


def test_update_missing_ext_id(handler):
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    with pytest.raises(ValueError):
        handler.update("entityA", {"body": {"name": "foo"}})


def test_update_missing_body(handler):
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    with pytest.raises(ValueError):
        handler.update("entityA", {"ext_id": "abc"})


def test_update_unsupported_entity(handler):
    handler.entity_metadata_map.pop("not_supported", None)
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    with pytest.raises(ValueError):
        handler.update("not_supported", {"body": {"name": "foo"}, "ext_id": "abc"})


def test_update_not_supported(handler):
    handler.entity_metadata_map["entityA"]["update_supported"] = "False"
    with pytest.raises(ValueError):
        handler.update("entityA", {"body": {"name": "foo"}, "ext_id": "abc"})


def test_update_etag_error(handler):
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": True,
        "delete": False,
    }
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"data": {}}
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._get_tag = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.update("entityA", {"body": {"name": "foo"}, "ext_id": "abc"})


def test_update_execute_method_error(handler):
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    handler._get_api_client = MagicMock(return_value=MagicMock())
    handler._get_tag = MagicMock(return_value="etag")
    handler._execute_method_with_task_monitor = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.update("entityA", {"body": {"name": "foo"}, "ext_id": "abc"})


def test_delete_success(handler):
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")
    extid = handler.delete("entityA", "abc")
    assert extid == "abc"


def test_delete_unsupported_entity(handler):
    with pytest.raises(ValueError):
        handler.delete("not_supported", "abc")


def test_delete_etag_required(handler):
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["delete_etag_required"] = True
    handler._get_api_client = MagicMock(return_value=MagicMock())
    handler._get_tag = MagicMock(return_value="etag")
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")
    extid = handler.delete("entityA", "abc")
    assert extid == "abc"


def test_delete_etag_error(handler):
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": False,
        "delete": True,
    }
    handler._get_api_client = MagicMock(return_value=MagicMock())
    handler._get_tag = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.delete("entityA", "abc")


def test_delete_execute_method_error(handler):
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler._execute_method_with_task_monitor = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.delete("entityA", "abc")


def test_ensure_entity_noop_when_already_loaded(handler: DomainEntityHandler) -> None:
    """ensure_entity is a no-op when the entity is already initialized."""
    names = set(handler.entity_names)
    handler.ensure_entity("entityA")
    assert handler.entity_names == names


def test_ensure_entity_unknown_raises(handler: DomainEntityHandler) -> None:
    """ensure_entity raises when the entity is not in the metadata map."""
    with pytest.raises(ValueError, match="Unsupported entity"):
        handler.ensure_entity("no_such_entity")


def test_ensure_entity_initializes_new_entity(handler: DomainEntityHandler) -> None:
    """ensure_entity initializes SDK clients for an entity not yet loaded."""
    handler.entity_metadata_map["entityD"] = {
        "sdk_name": "sdk_mod",
        "api_class_path": "api_d",
        "list_method_name": "list_entityDs",
    }
    handler._initialize_config = MagicMock()
    handler._initialize_client = MagicMock()
    handler._initialize_entity_crud_mapping = MagicMock()
    handler.ensure_entity("entityD")
    assert "entityD" in handler.entity_names
    handler._initialize_config.assert_called_once_with("entityD")
    handler._initialize_client.assert_called_once_with("entityD")
    handler._initialize_entity_crud_mapping.assert_called_once_with("entityD")


def test_ensure_entity_uses_ztf_helper(handler: DomainEntityHandler) -> None:
    """ensure_entity routes helper entities through the custom-helper path."""
    handler.entity_metadata_map["helper_ent"] = {"use_ztf_helper": True}
    handler._initialize_ztf_helper = MagicMock()
    handler.ensure_entity("helper_ent")
    handler._initialize_ztf_helper.assert_called_once_with("helper_ent")
    assert "helper_ent" in handler.entity_names


def test_list_entities(handler):
    api_instance = MagicMock()
    api_instance.list_entityAs.return_value = MagicMock(
        metadata=MagicMock(total_available_results=1), data=[{"foo": "bar"}]
    )
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    result = handler.list_entities("entityA")
    assert isinstance(result, list)


def test_list_entities_paged(handler):
    api_instance = MagicMock()
    # Simulate two pages
    api_instance.list_entityAs.side_effect = [
        MagicMock(metadata=MagicMock(total_available_results=2), data=[{"foo": "bar"}]),
        MagicMock(data=[{"foo": "baz"}]),
    ]
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    result = handler.list_entities("entityA")
    assert isinstance(result, list)


def test_list_entities_passes_kwargs_across_pages(handler):
    api_instance = MagicMock()
    calls = []

    def list_entity_as(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return MagicMock(
                metadata=MagicMock(total_available_results=2), data=[{"foo": "bar"}]
            )
        return MagicMock(
            metadata=MagicMock(total_available_results=2), data=[{"foo": "baz"}]
        )

    api_instance.list_entityAs.side_effect = list_entity_as
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.list_entities("entityA", _filter="name eq 'foo'", _select="extId", _limit=1)

    assert calls[0]["_filter"] == "name eq 'foo'"
    assert calls[0]["_select"] == "extId"
    assert calls[0]["_limit"] == 1
    assert calls[1]["_filter"] == "name eq 'foo'"
    assert calls[1]["_select"] == "extId"
    assert calls[1]["_limit"] == 1
    assert calls[1]["_page"] == 1


def test_list_entities_hard_page_cap_prevents_infinite_loop(handler, monkeypatch):
    """Stale ``total_available_results`` must not loop forever."""
    monkeypatch.setattr(handler, "_MAX_PAGINATION_PAGES", 5, raising=False)

    api_instance = MagicMock()

    def list_entity_as(**kwargs):
        return MagicMock(
            metadata=MagicMock(total_available_results=10_000),
            data=[{"n": kwargs.get("_page", 0)}],
        )

    api_instance.list_entityAs.side_effect = list_entity_as
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance

    result = handler.list_entities("entityA")
    # 1 initial call + up to (MAX-1) paginated calls before the cap breaks us out.
    assert len(api_instance.list_entityAs.mock_calls) <= 5
    assert isinstance(result, list)
    assert len(result) < 10_000


def test_list_entities_forward_progress_guard(handler):
    """A page that returns empty data breaks the loop cleanly."""
    api_instance = MagicMock()
    api_instance.list_entityAs.side_effect = [
        MagicMock(metadata=MagicMock(total_available_results=5), data=[{"n": 1}]),
        MagicMock(data=[]),
    ]
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    result = handler.list_entities("entityA")
    assert result == [{"n": 1}]


def test_list_entities_handles_total_less_than_initial(handler):
    """If total_available_results < rows already fetched, we return what we have."""
    api_instance = MagicMock()
    api_instance.list_entityAs.return_value = MagicMock(
        metadata=MagicMock(total_available_results=0),
        data=[{"foo": "bar"}, {"foo": "baz"}],
    )
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    result = handler.list_entities("entityA")
    assert result == [{"foo": "bar"}, {"foo": "baz"}]
    api_instance.list_entityAs.assert_called_once()


def test_get_entity_by_ext_id(handler):
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock(data="entity_obj")
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    result = handler.get_entity_by_ext_id("entityA", "abc")
    assert result == "entity_obj"


def test_sanitize_entity_data(handler):
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"foo": "bar"}
    handler._get_api_client = MagicMock(return_value=api_client)
    data = MagicMock()
    data.data = MagicMock()
    result = handler.sanitize_entity_data("entityA", data)
    assert result == {"foo": "bar"}


def test_sanitize_entity_data_empty(handler):
    with pytest.raises(ValueError):
        handler.sanitize_entity_data("entityA", None)
    data = MagicMock()
    data.data = None
    with pytest.raises(ValueError):
        handler.sanitize_entity_data("entityA", data)


def test_get_entity_by_identifier_ext_id(handler):
    handler.get_entity_by_ext_id = MagicMock(return_value="entity_obj")
    handler.entity_cache = {}
    result, extid = handler.get_entity_by_identifier("entityA", None, ext_id="abc")
    assert result == "entity_obj"


def test_get_entity_by_identifier_filter(handler):
    handler.list_entities = MagicMock(return_value=[MagicMock()])
    handler.entity_cache = {}
    result, _ = handler.get_entity_by_identifier("entityA", "name eq 'foo'")
    assert result is not None


def test_get_entity_by_identifier_cache(handler):
    # Cache keys are typed tuples (entity, "filter", filter_string) --
    # see Phase E item E4 (collision-free cache keys).
    handler.entity_cache = {("entityA", "filter", "name eq 'foo'"): "cached_obj"}
    result, _ = handler.get_entity_by_identifier("entityA", "name eq 'foo'")
    assert result == "cached_obj"


class TestEntityCacheKeyStructure:
    """E4 regression suite: cache keys are collision-proof tuples."""

    def test_filter_and_extid_lookups_dont_collide(self, handler) -> None:
        # Populate via the filter path and the ext_id path with payloads
        # that would collapse to the same string under the old
        # ``f"{entity}_{joined}"`` scheme.
        handler.list_entities = MagicMock(return_value=[MagicMock(name="filter_obj")])
        handler.get_entity_by_ext_id = MagicMock(
            return_value=MagicMock(name="extid_obj")
        )
        handler.entity_cache = {}

        handler.get_entity_by_identifier("entityA", "abc")
        handler.get_entity_by_identifier("entityA", None, ext_id="abc")

        keys = list(handler.entity_cache)
        assert len(keys) == 2, f"Expected two distinct cache entries, got {keys!r}"
        assert any(k[:2] == ("entityA", "filter") for k in keys)
        assert any(k[:2] == ("entityA", "extId") for k in keys)

    def test_underscore_payloads_do_not_collide(self, handler) -> None:
        # Two ext_id kwargs that, under the old ``"_".join(str(v) for v
        # in kwargs.values())`` scheme, would produce the same cache
        # string now produce distinct tuple keys.
        calls: list[dict] = []

        def _by_ext_id(entity, ext_id):
            calls.append({"ext_id": ext_id})
            return f"obj_for_{ext_id}"

        handler.get_entity_by_ext_id = _by_ext_id
        handler.entity_cache = {}

        r1, _ = handler.get_entity_by_identifier(
            "entityA", None, ext_id="a_b", name="c"
        )
        r2, _ = handler.get_entity_by_identifier(
            "entityA", None, ext_id="a", name="b_c"
        )
        # Different lookups must produce different SDK calls and cache
        # entries (the old code would join to ``entityA_a_b_c`` for
        # both).
        assert r1 != r2
        assert len(handler.entity_cache) == 2

    def test_kwargs_order_does_not_create_second_cache_entry(self, handler) -> None:
        # The tuple sort makes key ordering deterministic, so two logically
        # identical calls with different Python kwarg insertion order
        # resolve to the SAME cache key.
        handler.get_entity_by_ext_id = MagicMock(return_value="shared_obj")
        handler.entity_cache = {}

        handler.get_entity_by_identifier("entityA", None, ext_id="id1", name="n")
        handler.get_entity_by_identifier("entityA", None, name="n", ext_id="id1")
        assert len(handler.entity_cache) == 1
        # And the underlying SDK call happened exactly once (second call
        # was served from cache).
        assert handler.get_entity_by_ext_id.call_count == 1

    def test_unhashable_kwarg_value_is_reprified(self, handler) -> None:
        # A dict in kwargs can't be used directly as a tuple element;
        # the cache key must still be hashable. ``repr`` stringifies it
        # stably so the cache survives.
        handler.get_entity_by_ext_id = MagicMock(return_value="obj")
        handler.entity_cache = {}

        handler.get_entity_by_identifier(
            "entityA", None, ext_id="xyz", extra={"k": "v"}
        )
        assert len(handler.entity_cache) == 1
        # Key must be hashable (no TypeError in dict lookup below).
        _ = hash(next(iter(handler.entity_cache)))


def test_get_entity_by_identifier_none(handler):
    handler.list_entities = MagicMock(return_value=[])
    handler.entity_cache = {}
    result, _ = handler.get_entity_by_identifier("entityA", "name eq 'foo'")
    assert result is None


def test_get_entity_by_identifier_no_filter_no_ext_id(handler):
    with pytest.raises(ValueError, match="Either extId or ext_id must be provided"):
        handler.get_entity_by_identifier("entityA", None)


def test_monitor_task_success(handler):
    monitor = MagicMock()
    monitor.monitor.return_value = (
        True,
        "SUCCEEDED",
        MagicMock(to_dict=lambda: {"foo": "bar"}),
    )
    with patch("ztf.entity_wrapper.entity_handler.PcTaskMonitor", return_value=monitor):
        handler.sdk_api_client_map["ntnx_prism_py_client"] = MagicMock()
        result = handler._monitor_task("taskid")
        assert result == {"foo": "bar"}


def test_handler_reads_task_timeout_from_config(entity_map_patch):
    """Regression for 4.4: ``task_timeout_seconds`` / interval are read
    from ``global_config.config`` and forwarded to ``PcTaskMonitor``."""
    global_config = {
        "config": {
            "host": "1.2.3.4",
            "username": "admin",
            "password": "pass",
            "task_timeout_seconds": 120,
            "task_check_interval_seconds": 2,
        }
    }
    with patch("importlib.import_module") as import_mod:
        sdk_mod = MagicMock()
        sdk_mod.Configuration.return_value = MagicMock()
        sdk_mod.api_client.ApiClient.return_value = MagicMock()
        import_mod.return_value = sdk_mod
        eh = DomainEntityHandler({"entityA"}, global_config)
    assert eh.task_timeout_seconds == 120
    assert eh.task_check_interval_seconds == 2


def test_monitor_task_forwards_configured_timeouts(entity_map_patch):
    """The configured timeouts are passed to ``PcTaskMonitor`` on each call."""
    global_config = {
        "config": {
            "host": "1.2.3.4",
            "username": "admin",
            "password": "pass",
            "task_timeout_seconds": 77,
            "task_check_interval_seconds": 4,
        }
    }
    with patch("importlib.import_module") as import_mod:
        sdk_mod = MagicMock()
        sdk_mod.Configuration.return_value = MagicMock()
        sdk_mod.api_client.ApiClient.return_value = MagicMock()
        import_mod.return_value = sdk_mod
        eh = DomainEntityHandler({"entityA"}, global_config)

    eh.sdk_api_client_map["ntnx_prism_py_client"] = MagicMock()
    monitor = MagicMock()
    monitor.monitor.return_value = (
        True,
        "SUCCEEDED",
        MagicMock(to_dict=lambda: {"foo": "bar"}),
    )
    with patch(
        "ztf.entity_wrapper.entity_handler.PcTaskMonitor",
        return_value=monitor,
    ) as mock_mon:
        eh._monitor_task("taskid")
    _, kwargs = mock_mon.call_args
    assert kwargs["timeout_seconds"] == 77
    assert kwargs["check_interval_seconds"] == 4


def test_monitor_task_converts_snake_case(handler):
    monitor = MagicMock()
    monitor.monitor.return_value = (
        True,
        "SUCCEEDED",
        MagicMock(
            to_dict=lambda: {
                "ext_id": "task-1",
                "entities_affected": [{"entityA_ext_id": "abc"}],
            }
        ),
    )
    with patch("ztf.entity_wrapper.entity_handler.PcTaskMonitor", return_value=monitor):
        handler.sdk_api_client_map["ntnx_prism_py_client"] = MagicMock()
        result = handler._monitor_task("taskid")
        assert result["extId"] == "task-1"
        assert result["entitiesAffected"][0]["entityAExtId"] == "abc"


def test_monitor_task_timeout(handler):
    monitor = MagicMock()
    # Simulate a quick timeout to avoid infinite loop
    monitor.monitor.return_value = (
        False,
        "Timed out",
        MagicMock(to_dict=lambda: {"foo": "bar"}),
    )
    with patch("ztf.entity_wrapper.entity_handler.PcTaskMonitor", return_value=monitor):
        handler.sdk_api_client_map["ntnx_prism_py_client"] = MagicMock()
        result = handler._monitor_task("taskid")
        assert result == {"foo": "bar"}


def test_monitor_task_failed(handler):
    monitor = MagicMock()
    error_msg = MagicMock(message="fail")
    # Simulate a failed task with error messages and avoid infinite loop
    monitor.monitor.return_value = (
        False,
        "FAILED",
        MagicMock(to_dict=lambda: {"foo": "bar"}, error_messages=[error_msg]),
    )
    with patch("ztf.entity_wrapper.entity_handler.PcTaskMonitor", return_value=monitor):
        handler.sdk_api_client_map["ntnx_prism_py_client"] = MagicMock()
        with pytest.raises(Exception):
            handler._monitor_task("taskid")


def test__get_tag_success(handler):
    api_client = MagicMock()
    api_client.get_etag.return_value = "etag123"
    handler.get_entity_by_ext_id = MagicMock(return_value="entity_obj")
    tag = handler._get_tag("entityA", "extid", api_client)
    assert tag == "etag123"


def test__get_tag_exception(handler):
    api_client = MagicMock()
    handler.get_entity_by_ext_id = MagicMock(side_effect=Exception("fail"))
    api_client = MagicMock()
    with pytest.raises(Exception):
        handler._get_tag("entityA", "extid", api_client)


def test_get_tag_error(handler):
    handler.get_entity_by_ext_id = MagicMock(side_effect=Exception("fail"))
    api_client = MagicMock()
    with pytest.raises(Exception):
        handler._get_tag("entityA", "extid", api_client)


def test__execute_method_with_task_monitor_task_reference(handler):
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    method.return_value = response
    handler._monitor_task = MagicMock(
        return_value={"entitiesAffected": [{"extId": "abc"}]}
    )
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id == "abc"


def test__execute_method_with_task_monitor_task_reference_with_entity_extid(handler):
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    method.return_value = response
    handler._monitor_task = MagicMock(return_value={"entityAExtId": "abc"})
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id == "abc"


def test__execute_method_with_task_monitor_task_reference_no_entities_affected(handler):
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    method.return_value = response
    handler._monitor_task = MagicMock(return_value={"extId": "foo=:abc"})
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id == "abc"


def test__execute_method_with_task_monitor_task_reference_no_ext_id(handler):
    """When task response has no ext_id, return None (caller decides to raise)."""
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    method.return_value = response
    handler._monitor_task = MagicMock(return_value={})
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id is None


def test_monitor_task_error(handler):
    class DummyResponse:
        def to_dict(self):
            return {
                "error_messages": [MagicMock(message="err")],
                "legacy_error_message": "legacy",
            }

        error_messages = [MagicMock(message="err")]
        legacy_error_message = "legacy"
        entities_affected = None
        ext_id = "id"

    monitor = MagicMock(return_value=(True, "FAILED", DummyResponse()))
    with (
        patch("ztf.state_monitor.task_monitor.PcTaskMonitor.monitor", monitor),
        pytest.raises(Exception),
    ):
        handler._monitor_task("extid")


def test__execute_method_with_task_monitor_normal_object(handler):
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    response = MagicMock()
    response.data.ext_id = "abc"
    response.data._object_type = None
    response.data.to_dict.return_value = {"foo": "bar"}
    method.return_value = response
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id == "abc"


def test__execute_method_with_task_monitor_no_response(handler):
    """Empty/None response returns None (valid for 202 update/delete)."""
    api_instance = MagicMock()
    method = MagicMock()
    api_instance.create_entityA = method
    method.return_value = None
    ext_id = handler._execute_method_with_task_monitor(
        api_instance, "create_entityA", entity="entityA"
    )
    assert ext_id is None


def test_sanitize_entity_data_no_data(handler):
    data = MagicMock()
    data.data = None
    with pytest.raises(ValueError):
        handler.sanitize_entity_data("entityA", data)


def test_get_entity_by_identifier_error(handler):
    handler.list_entities = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.get_entity_by_identifier("entityA", _filter="name eq 'foo'")


def test_init_unsupported_entity(global_config):
    with pytest.raises(ValueError):
        DomainEntityHandler({"not_supported"}, global_config)


def test_create_get_entity_by_identifier_exception(handler):
    handler.get_entity_by_identifier = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})


def test_create_update_delete_execute_method_with_task_monitor_exception(handler):
    # with patch("threading.Lock", DummyLock):
    handler._execute_method_with_task_monitor = MagicMock(side_effect=Exception("fail"))
    handler.list_entities = MagicMock(return_value=[])
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    # create
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})
    # update
    with pytest.raises(Exception):
        handler.update("entityA", {"body": {"name": "foo"}, "ext_id": "abc"})
    # delete
    with pytest.raises(Exception):
        handler.delete("entityA", "abc")
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": False,
        "delete": True,
    }
    handler._get_tag = MagicMock(return_value="etag")
    # delete with etag required - still fails in _execute_method_with_task_monitor
    with pytest.raises(Exception):
        handler.delete("entityA", "abc")


# ---------------------------------------------------------------------------
# _load_compat_map tests
# ---------------------------------------------------------------------------


def test_load_compat_map_file_missing(monkeypatch):
    """When compat map file does not exist, return empty dict."""
    import ztf.entity_wrapper.entity_handler as eh
    from ztf.entity_wrapper.entity_handler import _load_compat_map

    monkeypatch.setattr(eh, "_compat_map_cache", None)
    from pathlib import Path

    result = _load_compat_map(Path("/nonexistent/compat.json"))
    assert result == {}
    # Reset cache
    monkeypatch.setattr(eh, "_compat_map_cache", None)


def test_load_compat_map_cache_hit(monkeypatch):
    """Second call returns cached dict without re-reading file."""
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(eh, "_compat_map_cache", {"cached": True})
    result = eh._load_compat_map()
    assert result == {"cached": True}
    monkeypatch.setattr(eh, "_compat_map_cache", None)


# ---------------------------------------------------------------------------
# _get_parent_kwargs tests
# ---------------------------------------------------------------------------


def test_get_parent_kwargs_with_param(handler):
    handler.entity_metadata_map["entityA"]["parent_id_param"] = "clusterExtId"
    result = handler._get_parent_kwargs("entityA", {"clusterExtId": "abc"})
    assert result == {"clusterExtId": "abc"}


def test_get_parent_kwargs_snake_fallback(handler):
    handler.entity_metadata_map["entityA"]["parent_id_param"] = "clusterExtId"
    result = handler._get_parent_kwargs("entityA", {"cluster_ext_id": "abc"})
    assert result == {"clusterExtId": "abc"}


def test_get_parent_kwargs_no_param(handler):
    handler.entity_metadata_map["entityA"].pop("parent_id_param", None)
    result = handler._get_parent_kwargs("entityA", {"foo": "bar"})
    assert result == {}


def test_get_parent_kwargs_value_missing(handler):
    handler.entity_metadata_map["entityA"]["parent_id_param"] = "clusterExtId"
    result = handler._get_parent_kwargs("entityA", {"other": "val"})
    assert result == {}


# ---------------------------------------------------------------------------
# _build_method_kwargs tests
# ---------------------------------------------------------------------------


def test_build_method_kwargs_with_params(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {
        "create": ["body", "clusterExtId"],
    }
    result = handler._build_method_kwargs(
        "entityA", "create", body={"name": "x"}, clusterExtId="abc"
    )
    assert result == {"body": {"name": "x"}, "clusterExtId": "abc"}


def test_build_method_kwargs_underscore_param(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {
        "create": ["body", "_hidden"],
    }
    result = handler._build_method_kwargs(
        "entityA", "create", body={"a": 1}, _hidden="secret"
    )
    assert result == {"body": {"a": 1}, "_hidden": "secret"}


def test_build_method_kwargs_no_params_get(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {}
    result = handler._build_method_kwargs("entityA", "get", ext_id="abc", parentId="p1")
    assert result["extId"] == "abc"
    assert result["parentId"] == "p1"


def test_build_method_kwargs_no_params_delete(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {}
    result = handler._build_method_kwargs("entityA", "delete", ext_id="abc")
    assert result["extId"] == "abc"


def test_build_method_kwargs_no_params_create(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {}
    result = handler._build_method_kwargs("entityA", "create", body={"n": 1}, extra="x")
    assert result == {"body": {"n": 1}, "extra": "x"}


def test_build_method_kwargs_extid_param(handler):
    handler.entity_metadata_map["entityA"]["method_params"] = {
        "get": ["extId"],
    }
    result = handler._build_method_kwargs("entityA", "get", ext_id="abc")
    assert result == {"extId": "abc"}


def test_build_method_kwargs_no_params_update_shares_create_logic(handler):
    """``update`` falls through to the shared ``body`` branch alongside ``create``.

    The Phase D refactor collapsed the create/update fallback branches
    into a single table lookup; this test pins down that ``update``
    still produces the same shape as ``create`` when ``method_params``
    is absent.
    """
    handler.entity_metadata_map["entityA"]["method_params"] = {}
    result = handler._build_method_kwargs(
        "entityA", "update", body={"n": 1}, extId="abc"
    )
    assert result == {"body": {"n": 1}, "extId": "abc"}


def test_build_method_kwargs_no_params_unknown_operation_returns_empty(handler):
    """Operations outside create/update/get/delete fall through cleanly."""
    handler.entity_metadata_map["entityA"]["method_params"] = {}
    result = handler._build_method_kwargs("entityA", "custom_op", foo="bar")
    assert result == {}


# ---------------------------------------------------------------------------
# _default_method_name helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operation", "entity", "expected"),
    [
        ("create", "vm", "create_vm"),
        ("update", "vm", "update_vm_by_id"),
        ("delete", "vm", "delete_vm_by_id"),
        ("get", "vm", "get_vm_by_id"),
        ("list", "vm", "list_vms"),
        ("list", "category", "list_categories"),
    ],
)
def test_default_method_name_matches_sdk_conventions(operation, entity, expected):
    assert _default_method_name(operation, entity) == expected


# ---------------------------------------------------------------------------
# _get_readonly_fields_for_entity_operation tests
# ---------------------------------------------------------------------------


def test_readonly_fields_no_namespace(handler):
    handler.entity_metadata_map["entityA"]["namespace"] = None
    assert (
        handler._get_readonly_fields_for_entity_operation("entityA", "create") == set()
    )


def test_readonly_fields_no_method(handler):
    handler.entity_metadata_map["entityA"]["create_method_name"] = ""
    assert (
        handler._get_readonly_fields_for_entity_operation("entityA", "create") == set()
    )


def test_readonly_fields_with_schema(handler, monkeypatch):
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(
        eh,
        "_compat_map_cache",
        {
            "test": {
                "createEntityA": {
                    "schema": {
                        "request": {
                            "name": {"readOnly": False},
                            "extId": {"readOnly": True},
                        }
                    }
                }
            }
        },
    )
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entity_a"
    result = handler._get_readonly_fields_for_entity_operation("entityA", "create")
    assert "extId" in result
    assert "name" not in result
    monkeypatch.setattr(eh, "_compat_map_cache", None)


# ---------------------------------------------------------------------------
# _prepare_update_body tests
# ---------------------------------------------------------------------------


def test_prepare_update_body_strips_empty_strings(handler):
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {
        "data": {"name": "old", "desc": "", "nested": {"a": "", "b": "val"}}
    }
    result = handler._prepare_update_body(
        MagicMock(), {"name": "new"}, api_client, readonly_fields=set()
    )
    assert result["name"] == "new"
    assert "desc" not in result
    assert result["nested"] == {"b": "val"}


def test_prepare_update_body_no_data_key(handler):
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"name": "old"}
    result = handler._prepare_update_body(MagicMock(), {"name": "new"}, api_client)
    assert result["name"] == "new"


def test_prepare_update_body_non_dict_response(handler):
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = "not_a_dict"
    result = handler._prepare_update_body(MagicMock(), {"name": "val"}, api_client)
    assert result == {"name": "val"}


# ---------------------------------------------------------------------------
# _is_etag_required tests
# ---------------------------------------------------------------------------


def test_etag_required_dict(handler):
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": True,
        "delete": False,
    }
    assert handler._is_etag_required("entityA", "update") is True
    assert handler._is_etag_required("entityA", "delete") is False


def test_etag_required_legacy_delete(handler):
    handler.entity_metadata_map["entityA"]["etag_required"] = None
    handler.entity_metadata_map["entityA"]["delete_etag_required"] = True
    assert handler._is_etag_required("entityA", "delete") is True


def test_etag_required_legacy_update(handler):
    handler.entity_metadata_map["entityA"]["etag_required"] = None
    assert handler._is_etag_required("entityA", "update") is True


# ---------------------------------------------------------------------------
# _get_target_version tests
# ---------------------------------------------------------------------------


def test_get_target_version_success(handler):
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.1.b1")
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    assert handler._get_target_version("entityA") == 4.1


def test_get_target_version_no_client(handler):
    handler.entity_metadata_map["entityA"]["sdk_name"] = "missing_sdk"
    assert handler._get_target_version("entityA") is None


def test_get_target_version_no_version(handler):
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version=None)
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    assert handler._get_target_version("entityA") is None


def test_get_target_version_bad_format(handler):
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="latest")
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    assert handler._get_target_version("entityA") is None


# ---------------------------------------------------------------------------
# _negotiate_schema tests
# ---------------------------------------------------------------------------


def test_negotiate_schema_non_dict(handler):
    assert handler._negotiate_schema("entityA", "create_entityA", "raw") == "raw"


def test_negotiate_schema_no_namespace(handler):
    handler.entity_metadata_map["entityA"]["namespace"] = None
    assert handler._negotiate_schema("entityA", "m", {"a": 1}) == {"a": 1}


def test_negotiate_schema_no_version(handler):
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version=None)
    assert handler._negotiate_schema("entityA", "m", {"a": 1}) == {"a": 1}


def test_negotiate_schema_full_filtering(handler, monkeypatch):
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(
        eh,
        "_compat_map_cache",
        {
            "test": {
                "createEntityA": {
                    "schema": {
                        "request": {
                            "name": {"versions": [4.0, 4.1]},
                            "newField": {"versions": [4.1]},
                        }
                    }
                }
            }
        },
    )
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.0")
    body = {"name": "foo", "newField": "bar"}
    result = handler._negotiate_schema("entityA", "create_entity_a", body)
    assert "name" in result
    assert "newField" not in result
    monkeypatch.setattr(eh, "_compat_map_cache", None)


def test_negotiate_schema_uses_exact_catalog_operation_id(handler, monkeypatch):
    """Schema lookup does not infer operation IDs from SDK method spelling."""
    import ztf.entity_wrapper.entity_handler as eh

    runtime_operation = RuntimeOperation(
        key="test|POST|/config/items|createAnIDP",
        canonical_entity="entityA",
        public_name="create",
        operation_id="createAnIDP",
        kind="crud",
        lifecycle_role="create",
        package="sdk-mod",
        module="sdk_mod.api.api_a",
        api_class="ApiA",
        method="create_an_idp",
    )
    handler.runtime_catalog = MagicMock()
    handler.runtime_catalog.resolve_method.return_value = runtime_operation
    monkeypatch.setattr(
        eh,
        "_compat_map_cache",
        {
            "test": {
                "createAnIDP": {
                    "schema": {
                        "request": {
                            "name": {"versions": [4.0]},
                            "newField": {"versions": [4.1]},
                        }
                    }
                }
            }
        },
    )
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.0")

    result = handler._negotiate_schema(
        "entityA",
        "create_an_idp",
        {"name": "kept", "newField": "removed"},
    )

    assert result == {"name": "kept"}
    monkeypatch.setattr(eh, "_compat_map_cache", None)


def test_negotiate_schema_empty_compat(handler, monkeypatch):
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(eh, "_compat_map_cache", {})
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.0")
    assert handler._negotiate_schema("entityA", "m", {"a": 1}) == {"a": 1}
    monkeypatch.setattr(eh, "_compat_map_cache", None)


# ---------------------------------------------------------------------------
# strip_readonly_fields tests
# ---------------------------------------------------------------------------


def test_strip_readonly_fields_non_dict(handler):
    assert handler.strip_readonly_fields("entityA", "raw") == "raw"


def test_strip_readonly_fields_no_method_name(handler):
    handler.entity_metadata_map["entityA"]["create_method_name"] = ""
    body = {"name": "foo"}
    assert handler.strip_readonly_fields("entityA", body) == body


def test_strip_readonly_fields_removes_readonly(handler, monkeypatch):
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(
        eh,
        "_compat_map_cache",
        {
            "test": {
                "createEntityA": {
                    "schema": {
                        "request": {
                            "name": {"readOnly": False, "versions": [4.0]},
                            "createTime": {"readOnly": True, "versions": [4.0]},
                            "ownerExtId": {"readOnly": True, "versions": [4.0]},
                        }
                    }
                }
            }
        },
    )
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entity_a"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.0")

    body = {
        "name": "tiny-linux",
        "createTime": "2026-08-31T15:14:47.309878+00:00",
        "ownerExtId": "ae1c33bd-f0dd-5000-9e36-49247c0d1b67",
    }
    result = handler.strip_readonly_fields("entityA", body)

    assert result == {"name": "tiny-linux"}
    monkeypatch.setattr(eh, "_compat_map_cache", None)


def test_strip_readonly_fields_update_operation_uses_update_method(
    handler, monkeypatch
):
    import ztf.entity_wrapper.entity_handler as eh

    monkeypatch.setattr(
        eh,
        "_compat_map_cache",
        {
            "test": {
                "updateEntityA": {
                    "schema": {
                        "request": {
                            "name": {"readOnly": False, "versions": [4.0]},
                            "lastUpdateTime": {"readOnly": True, "versions": [4.0]},
                        }
                    }
                }
            }
        },
    )
    handler.entity_metadata_map["entityA"]["namespace"] = "test"
    handler.entity_metadata_map["entityA"]["sdk_name"] = "sdk_mod"
    handler.entity_metadata_map["entityA"]["update_method_name"] = "update_entity_a"
    handler.sdk_api_client_map["sdk_mod"] = MagicMock(negotiated_version="v4.0")

    body = {"name": "tiny-linux", "lastUpdateTime": "2026-08-31T15:14:47+00:00"}
    result = handler.strip_readonly_fields("entityA", body, operation="update")

    assert result == {"name": "tiny-linux"}
    monkeypatch.setattr(eh, "_compat_map_cache", None)


# ---------------------------------------------------------------------------
# _filter_body_by_version tests
# ---------------------------------------------------------------------------


def test_filter_body_readonly_stripping(handler):
    schema = {"secret": {"readOnly": True}, "name": {"versions": [4.0]}}
    result = handler._filter_body_by_version(
        {"secret": "x", "name": "y"}, schema, 4.0, "test"
    )
    assert "secret" not in result
    assert result["name"] == "y"


def test_filter_body_version_filtering(handler):
    schema = {"old": {"versions": [4.0]}, "new": {"versions": [4.1]}}
    result = handler._filter_body_by_version(
        {"old": "a", "new": "b"}, schema, 4.0, "test"
    )
    assert "old" in result
    assert "new" not in result


def test_filter_body_oneof_variant(handler):
    schema = {
        "target": {
            "variants": {
                "IpTarget": {
                    "object_type": "v4.IpTarget",
                    "properties": {
                        "ip": {"versions": [4.0]},
                        "mask": {"versions": [4.1]},
                    },
                },
            }
        }
    }
    body = {
        "target": {
            "$objectType": "v4.IpTarget",
            "ip": "1.2.3.4",
            "mask": "255.255.0.0",
        }
    }
    result = handler._filter_body_by_version(body, schema, 4.0, "test")
    assert result["target"]["ip"] == "1.2.3.4"
    assert "mask" not in result["target"]


def test_filter_body_oneof_no_match(handler):
    schema = {
        "target": {
            "variants": {
                "IpTarget": {"object_type": "v4.IpTarget", "properties": {}},
            }
        }
    }
    body = {"target": {"$objectType": "v4.Unknown", "data": "x"}}
    result = handler._filter_body_by_version(body, schema, 4.0, "test")
    assert result["target"]["data"] == "x"


def test_filter_body_nested_object(handler):
    schema = {
        "config": {
            "properties": {
                "host": {"versions": [4.0]},
                "port": {"versions": [4.1]},
            }
        }
    }
    body = {"config": {"host": "x", "port": 443}}
    result = handler._filter_body_by_version(body, schema, 4.0, "test")
    assert result["config"]["host"] == "x"
    assert "port" not in result["config"]


def test_filter_body_nested_list(handler):
    schema = {
        "items": {
            "properties": {
                "name": {"versions": [4.0]},
                "extra": {"versions": [4.1]},
            }
        }
    }
    body = {"items": [{"name": "a", "extra": "b"}, "raw_item"]}
    result = handler._filter_body_by_version(body, schema, 4.0, "test")
    assert result["items"][0]["name"] == "a"
    assert "extra" not in result["items"][0]
    assert result["items"][1] == "raw_item"


def test_filter_body_unknown_field_passthrough(handler):
    schema = {"known": {"versions": [4.0]}}
    body = {"known": "a", "unknown": "b"}
    result = handler._filter_body_by_version(body, schema, 4.0, "test")
    assert result["known"] == "a"
    assert result["unknown"] == "b"


# ---------------------------------------------------------------------------
# _execute_method_with_task_monitor exception
# ---------------------------------------------------------------------------


def test_execute_method_exception(handler):
    api_instance = MagicMock()
    api_instance.bad_method.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        handler._execute_method_with_task_monitor(api_instance, "bad_method", "entityA")


def test_execute_method_entities_affected_entity_ext_id(handler):
    api_instance = MagicMock()
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    api_instance.op.return_value = response
    handler._monitor_task = MagicMock(
        return_value={"entitiesAffected": [{"entityAExtId": "specific_id"}]}
    )
    result = handler._execute_method_with_task_monitor(api_instance, "op", "entityA")
    assert result == "specific_id"


def test_execute_method_entities_affected_skips_known_parent_id(handler):
    """entitiesAffected[0] can be the parent entity the call was scoped to
    (e.g. creating a hardware-provider connection also lists the parent
    hardware provider ahead of the newly created connection). The parent's
    ext_id is already known (it was passed in as a request param), so it
    must be skipped in favor of the genuinely new entity."""
    api_instance = MagicMock()
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    api_instance.op.return_value = response
    handler._monitor_task = MagicMock(
        return_value={
            "entitiesAffected": [
                {
                    "extId": "parent-hardware-provider-id",
                    "rel": "lifecycle:config:hardware-providers",
                },
                {
                    "extId": "new-connection-id",
                    "rel": "lifecycle:config:hardware-provider-connections",
                },
            ]
        }
    )
    result = handler._execute_method_with_task_monitor(
        api_instance,
        "op",
        "entityA",
        hardwareProviderExtId="parent-hardware-provider-id",
    )
    assert result == "new-connection-id"


def test_execute_method_completion_details_uuid_preferred_over_task_id(handler):
    """Some task types (e.g. FC's CreatePatchedImageTask) report no
    entitiesAffected at all and only surface the real created-entity id via
    a completionDetails {name: "..._uuid", value: "<uuid>"} KV pair. The
    top-level 'extId' on that same task response is the *task's own* id
    (prefixed 'ergon:' upstream, already stripped by the time it reaches
    this dict) -- it must NOT be mistaken for the entity's id even though
    both are plausible-looking UUIDs. Confirmed live: this exact confusion
    silently corrupted fc_patched_image's stored ext_id, breaking every
    later reference (image_node, delete) to a uuid FC never assigned."""
    api_instance = MagicMock()
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    api_instance.op.return_value = response
    handler._monitor_task = MagicMock(
        return_value={
            "entitiesAffected": None,
            "extId": "task-own-id-not-the-entity",
            "completionDetails": [
                {"name": "patched_image_uuid", "value": "real-entity-uuid"},
                {"name": "patched_image_url", "value": "https://example/iso"},
            ],
        }
    )
    result = handler._execute_method_with_task_monitor(api_instance, "op", "entityA")
    assert result == "real-entity-uuid"


def test_execute_method_completion_details_skips_na_placeholder(handler):
    """completionDetails can report 'N/A' placeholders while a task is
    still RUNNING; only a real (non-'N/A') value should be accepted, and
    the code must otherwise still fall back to the task's own extId if no
    other id is ever found."""
    api_instance = MagicMock()
    response = MagicMock()
    response.data.ext_id = "taskid"
    response.data._object_type = "prism.v4.config.TaskReference"
    api_instance.op.return_value = response
    handler._monitor_task = MagicMock(
        return_value={
            "entitiesAffected": None,
            "extId": "ZXJnb24=:fallback-task-id",
            "completionDetails": [
                {"name": "patched_image_uuid", "value": "N/A"},
            ],
        }
    )
    result = handler._execute_method_with_task_monitor(api_instance, "op", "entityA")
    assert result == "fallback-task-id"


# ---------------------------------------------------------------------------
# create edge cases
# ---------------------------------------------------------------------------


def test_create_filter_key_error(handler):
    handler.entity_metadata_map["entityA"]["filter_format"] = "name eq '{missing_key}'"
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    with pytest.raises(Exception):
        handler.create("entityA", {"body": {"name": "foo"}})


def test_create_no_filter_format(handler):
    handler.entity_metadata_map["entityA"]["filter_format"] = None
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    response = MagicMock()
    response.data.ext_id = "new_id"
    response.data._object_type = None
    response.data.to_dict.return_value = {}
    handler.entity_metadata_map["entityA"][
        "api_instance"
    ].create_entityA.return_value = response
    ext_id = handler.create("entityA", {"body": {"name": "foo"}})
    assert ext_id == "new_id"


def test_create_not_supported(handler):
    handler.entity_metadata_map["entityA"]["create_supported"] = "False"
    with pytest.raises(ValueError, match="not supported"):
        handler.create("entityA", {"body": {"name": "foo"}})


# ---------------------------------------------------------------------------
# update with etag via per-call if_match kwarg (no shared-header mutation)
# ---------------------------------------------------------------------------


def test_update_etag_required_passes_if_match_kwarg(handler):
    """Etag is forwarded as a per-call ``if_match`` kwarg to the SDK method.

    Regression for Phase A: the legacy implementation mutated
    ``ApiClient.__default_headers`` under a per-SDK lock, serializing all
    etag-guarded updates.  The new flow passes ``if_match`` on the call
    itself so concurrent updates do not contend on a shared dict.
    """
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": True,
        "delete": False,
    }
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"data": {}}
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._get_tag = MagicMock(return_value="etag-value")
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")

    ext_id = handler.update("entityA", {"body": {"name": "new"}, "ext_id": "abc"})

    assert ext_id == "abc"
    # The shared-header mutation path is gone entirely.
    api_client.add_default_header.assert_not_called()
    # Etag is forwarded as a per-call kwarg.
    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["if_match"] == "etag-value"


def test_update_etag_execute_error(handler):
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": True,
        "delete": False,
    }
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"data": {}}
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._get_tag = MagicMock(return_value="etag-value")
    handler._execute_method_with_task_monitor = MagicMock(
        side_effect=Exception("api fail")
    )
    with pytest.raises(Exception):
        handler.update("entityA", {"body": {"name": "new"}, "ext_id": "abc"})


# ---------------------------------------------------------------------------
# Phase A regression tests
# ---------------------------------------------------------------------------


def test_update_subentity_with_parent_id_does_not_collide(handler):
    """Regression: sub-entities with ``parent_id_param`` + body update used
    to raise ``TypeError: got multiple values for keyword argument`` because
    the parent-id key stayed in ``data`` while also being merged in via
    ``**parent_kwargs``.  After Phase A, the parent key is popped from
    *data* so the unpack is collision-free.
    """
    meta = handler.entity_metadata_map["entityA"]
    meta["parent_id_param"] = "clusterExtId"
    meta["update_supported"] = "True"
    meta["etag_required"] = {"update": False, "delete": False}
    meta["method_params"] = {
        "create": ["body", "clusterExtId"],
        "get": ["extId", "clusterExtId"],
        "update": ["extId", "body", "clusterExtId"],
        "delete": ["extId", "clusterExtId"],
    }
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    meta["api_instance"] = api_instance
    meta["update_method_name"] = "update_entityA_by_id"
    api_client = MagicMock()
    api_client._ApiClient__sanitize_for_serialization.return_value = {"data": {}}
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._execute_method_with_task_monitor = MagicMock(return_value="child-ext")

    ext_id = handler.update(
        "entityA",
        {
            "body": {"name": "new"},
            "ext_id": "child-ext",
            "clusterExtId": "parent-ext",
        },
    )

    assert ext_id == "child-ext"
    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["clusterExtId"] == "parent-ext"
    # The GET call (for PUT semantics) must have been invoked exactly once
    # with both path params, not raised a TypeError pre-call.
    api_instance.get_entityA_by_id.assert_called_once()
    get_kwargs = api_instance.get_entityA_by_id.call_args[1]
    assert get_kwargs["clusterExtId"] == "parent-ext"
    assert get_kwargs["extId"] == "child-ext"


def test_update_subentity_snake_case_parent_id_is_normalised(handler):
    """``cluster_ext_id`` (snake_case) in ``data`` is normalised to the SDK's
    camelCase ``clusterExtId`` without colliding."""
    meta = handler.entity_metadata_map["entityA"]
    meta["parent_id_param"] = "clusterExtId"
    meta["update_supported"] = "True"
    meta["etag_required"] = {"update": False, "delete": False}
    meta["method_params"] = {
        "create": ["body", "clusterExtId"],
        "get": ["extId", "clusterExtId"],
        "update": ["extId", "body", "clusterExtId"],
        "delete": ["extId", "clusterExtId"],
    }
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = MagicMock()
    meta["api_instance"] = api_instance
    meta["update_method_name"] = "update_entityA_by_id"
    handler._get_api_client = MagicMock(return_value=MagicMock())
    handler._execute_method_with_task_monitor = MagicMock(return_value="child-ext")

    handler.update(
        "entityA",
        {
            "body": {"name": "new"},
            "ext_id": "child-ext",
            "cluster_ext_id": "parent-ext",
        },
    )

    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["clusterExtId"] == "parent-ext"


def test_delete_etag_required_passes_if_match_kwarg(handler):
    """Delete uses the same per-call ``if_match`` kwarg path (no lock)."""
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["delete_method_name"] = (
        "delete_entityA_by_id"
    )
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": False,
        "delete": True,
    }
    api_client = MagicMock()
    handler._get_api_client = MagicMock(return_value=api_client)
    handler._get_tag = MagicMock(return_value="delete-etag")
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")

    ext_id = handler.delete("entityA", "abc")

    assert ext_id == "abc"
    api_client.add_default_header.assert_not_called()
    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["if_match"] == "delete-etag"


def test_update_debug_log_redacts_password(handler, caplog):
    """DEBUG logs for update payloads must mask ``password`` values."""
    handler.entity_metadata_map["entityA"]["update_supported"] = "True"
    handler.entity_metadata_map["entityA"]["etag_required"] = {
        "update": False,
        "delete": False,
    }
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"][
        "api_instance"
    ].get_entityA_by_id.return_value = MagicMock()
    handler.entity_metadata_map["entityA"]["update_method_name"] = (
        "update_entityA_by_id"
    )
    handler._get_api_client = MagicMock(return_value=MagicMock())
    handler._execute_method_with_task_monitor = MagicMock(return_value="abc")

    secret = "hunter2-should-never-appear"
    with caplog.at_level(logging.DEBUG, logger="ztf.entity_wrapper.entity_handler"):
        handler.update(
            "entityA",
            {
                "body": {"name": "u", "password": secret},
                "ext_id": "abc",
                "resource_name": "r",
            },
        )

    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert secret not in joined
    assert "password" in joined.lower()
    assert "***" in joined


def test_etag_lock_attributes_are_removed(handler):
    """Phase A dropped the per-SDK etag lock; the attribute must not return."""
    assert not hasattr(handler, "_etag_locks")
    assert not hasattr(handler, "_get_etag_lock")


# ---------------------------------------------------------------------------
# run_operation tests
# ---------------------------------------------------------------------------


def test_run_operation_missing_type(handler):
    with pytest.raises(ValueError, match="type"):
        handler.run_operation("entityA", {})


def test_run_operation_unsupported(handler):
    handler.entity_metadata_map["entityA"]["operations"] = ["do_something"]
    with pytest.raises(ValueError, match="Unsupported"):
        handler.run_operation("entityA", {"type": "unknown_op"})


def test_run_operation_explicit_params(handler):
    """All params including IDs must be provided explicitly."""
    handler.entity_metadata_map["entityA"]["operations"] = ["do_something"]
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler._execute_method_with_task_monitor = MagicMock(return_value="result")
    result = handler.run_operation(
        "entityA",
        {
            "type": "do_something",
            "params": {"extId": "target-id"},
            "body": {"key": "val"},
        },
    )
    assert result == "result"
    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["extId"] == "target-id"
    assert call_kwargs["body"] == {"key": "val"}


def test_run_operation_uses_exact_catalog_adapter(handler, monkeypatch):
    """A moved operation dispatches through its operation-specific API class."""
    runtime_operation = RuntimeOperation(
        key="networking|POST|/config/virtual-switches/$actions/migrate|migrateBridge",
        canonical_entity="virtual_switch",
        public_name="migrate",
        operation_id="migrateBridge",
        kind="action",
        lifecycle_role=None,
        package="ntnx-networking-py-client",
        module="ntnx_networking_py_client.api.bridges_api",
        api_class="BridgesApi",
        method="migrate_bridge",
    )
    handler.runtime_catalog = MagicMock()
    handler.runtime_catalog.resolve_operation.return_value = runtime_operation
    handler.sdk_api_client_map["ntnx_networking_py_client"] = MagicMock()
    api_instance = MagicMock()
    api_class = MagicMock(return_value=api_instance)
    monkeypatch.setattr(handler, "_get_class_from_path", lambda *_: api_class)
    handler._execute_method_with_task_monitor = MagicMock(return_value="result")

    result = handler.run_operation(
        "entityA",
        {"type": "migrate", "params": {"extId": "target-id"}},
    )

    assert result == "result"
    api_class.assert_called_once_with(
        handler.sdk_api_client_map["ntnx_networking_py_client"]
    )
    call_args = handler._execute_method_with_task_monitor.call_args
    assert call_args.args[:3] == (api_instance, "migrate_bridge", "entityA")
    assert call_args.kwargs["extId"] == "target-id"


def test_run_operation_warns_and_rejects_legacy_owner(handler):
    """A stateless operation cannot dispatch through its released wrong owner."""
    handler.logger = MagicMock()
    handler._execute_method_with_task_monitor = MagicMock()

    with pytest.raises(
        ValueError,
        match="virtual_switch.*migrate",
    ):
        handler.run_operation("bridge", {"type": "migrate_bridge"})

    handler.logger.warning.assert_called_once()
    handler._execute_method_with_task_monitor.assert_not_called()


def test_update_warns_and_rejects_false_crud_lifecycle(handler):
    """A false CRUD form points users to the replacement operation syntax."""
    handler.logger = MagicMock()

    with pytest.raises(
        ValueError,
        match="user.*change_state",
    ):
        handler.update(
            "user_state",
            {"ext_id": "user-id", "body": {"state": "ACTIVE"}},
        )

    handler.logger.warning.assert_called_once()


def test_run_operation_exception(handler):
    handler.entity_metadata_map["entityA"]["operations"] = ["do_something"]
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler._execute_method_with_task_monitor = MagicMock(
        side_effect=RuntimeError("oops")
    )
    with pytest.raises(Exception):
        handler.run_operation("entityA", {"type": "do_something"})


# ---------------------------------------------------------------------------
# get_entity tests
# ---------------------------------------------------------------------------


def test_get_entity_with_ext_id(handler):
    handler.get_entity_by_ext_id = MagicMock(return_value="entity_obj")
    result = handler.get_entity("entityA", ext_id="abc")
    assert result == "entity_obj"
    handler.get_entity_by_ext_id.assert_called_once_with("entityA", "abc")


def test_get_entity_without_ext_id(handler):
    api_instance = MagicMock()
    api_instance.get_entityA_by_id.return_value = "raw_result"
    handler.entity_metadata_map["entityA"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityA"]["get_method_name"] = "get_entityA_by_id"
    result = handler.get_entity("entityA", someParam="val")
    assert result == "raw_result"


# ---------------------------------------------------------------------------
# delete not supported
# ---------------------------------------------------------------------------


def test_delete_not_supported(handler):
    handler.entity_metadata_map["entityA"]["delete_supported"] = "False"
    with pytest.raises(ValueError, match="not supported"):
        handler.delete("entityA", "abc")


# ---------------------------------------------------------------------------
# _initialize_client IAM branch
# ---------------------------------------------------------------------------


def test_initialize_client_iam(global_config, monkeypatch):
    iam_entity_map = {
        "iam_entity": {
            "sdk_name": "ntnx_iam_py_client",
            "api_class_path": "iam_api",
            "api_class_name": "IamApi",
            "namespace": "iam",
        },
        "task": {
            "sdk_name": "ntnx_prism_py_client",
            "api_class_path": "tasks_api",
            "api_class_name": "TasksApi",
        },
        "prism_task": {
            "sdk_name": "ntnx_prism_py_client",
            "api_class_path": "tasks_api",
            "api_class_name": "TasksApi",
        },
    }
    monkeypatch.setattr("ztf.entity_wrapper.entity_handler.entity_map", iam_entity_map)
    with patch("importlib.import_module") as import_mod:
        sdk_mod = MagicMock()
        sdk_mod.Configuration.return_value = MagicMock()
        # Simulate ApiClient without allow_version_negotiation param
        init_params = {"self": None, "configuration": None}
        sig = MagicMock()
        sig.parameters = init_params
        with patch("inspect.signature", return_value=sig):
            sdk_mod.api_client.ApiClient.return_value = MagicMock()
            import_mod.return_value = sdk_mod
            h = DomainEntityHandler({"iam_entity"}, global_config)
    client = h.sdk_api_client_map["ntnx_iam_py_client"]
    assert client.negotiated_version == "v4.1.b1"
    assert client.configuration.negotiation_completed is True


def test_initialize_client_version_negotiation(handler):
    """_initialize_client should monkey-patch negotiate_version and enable
    version negotiation when the ApiClient supports it."""
    import ztf.entity_wrapper.entity_handler as eh_mod

    test_sdk = "ntnx_nego_test_sdk"
    eh_mod._patched_api_clients.discard(test_sdk)

    handler.entity_metadata_map["entityNego"] = {
        "sdk_name": test_sdk,
        "api_class_path": "entity_api",
        "api_class_name": "EntityApi",
        "namespace": "prism",
    }
    handler.sdk_config_map[test_sdk] = MagicMock()

    sdk_mod = MagicMock()
    init_params = {
        "self": None,
        "configuration": None,
        "allow_version_negotiation": None,
    }
    sig = MagicMock()
    sig.parameters = init_params

    with (
        patch.object(eh_mod.importlib, "import_module", return_value=sdk_mod),
        patch.object(eh_mod.inspect, "signature", return_value=sig),
    ):
        handler._initialize_client("entityNego")

    client = handler.sdk_api_client_map[test_sdk]
    assert client.disable_minimum_supported_version_check is True
    assert test_sdk in eh_mod._patched_api_clients


# ---------------------------------------------------------------------------
# No-body entity create/update tests
# ---------------------------------------------------------------------------


def test_create_no_body_entity(handler):
    """Create dispatches fields as direct kwargs when method has no body param."""
    handler.entity_metadata_map["entityC"]["filter_format"] = None
    handler.entity_metadata_map["entityC"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityC"]["create_method_name"] = "create_entityC"
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    response = MagicMock()
    response.data.ext_id = "new_id"
    response.data._object_type = None
    response.data.to_dict.return_value = {}
    handler.entity_metadata_map["entityC"][
        "api_instance"
    ].create_entityC.return_value = response
    ext_id = handler.create(
        "entityC",
        {
            "name": "CAC",
            "isCertAuthEnabled": True,
            "dirSvcExtID": "abc-123",
        },
    )
    assert ext_id == "new_id"


def test_create_no_body_entity_no_error_without_body_key(handler):
    """No-body entity should NOT raise ValueError when 'body' key is absent."""
    handler.entity_metadata_map["entityC"]["filter_format"] = None
    handler.entity_metadata_map["entityC"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityC"]["create_method_name"] = "create_entityC"
    handler.sdk_api_client_map["sdk_mod"].negotiated_version = "v4.0"
    response = MagicMock()
    response.data.ext_id = "x"
    response.data._object_type = None
    response.data.to_dict.return_value = {}
    handler.entity_metadata_map["entityC"][
        "api_instance"
    ].create_entityC.return_value = response
    ext_id = handler.create("entityC", {"name": "test"})
    assert ext_id == "x"


def test_update_no_body_entity(handler):
    """Update dispatches fields as direct kwargs when method has no body param."""
    handler.entity_metadata_map["entityC"]["update_supported"] = "True"
    handler.entity_metadata_map["entityC"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityC"]["update_method_name"] = (
        "update_entityC_by_id"
    )
    handler._execute_method_with_task_monitor = MagicMock(return_value="ext_c")
    ext_id = handler.update(
        "entityC",
        {
            "ext_id": "ext_c",
            "name": "New Name",
            "isCertAuthEnabled": False,
        },
    )
    assert ext_id == "ext_c"
    call_kwargs = handler._execute_method_with_task_monitor.call_args[1]
    assert call_kwargs["name"] == "New Name"
    assert call_kwargs["isCertAuthEnabled"] is False
    assert "body" not in call_kwargs


def test_update_no_body_entity_skips_get_merge(handler):
    """No-body update should NOT call GET or prepare_update_body."""
    handler.entity_metadata_map["entityC"]["update_supported"] = "True"
    api_instance = MagicMock()
    handler.entity_metadata_map["entityC"]["api_instance"] = api_instance
    handler.entity_metadata_map["entityC"]["update_method_name"] = (
        "update_entityC_by_id"
    )
    handler._execute_method_with_task_monitor = MagicMock(return_value="ext_c")
    handler.update("entityC", {"ext_id": "ext_c", "name": "val"})
    api_instance.get_entityC_by_id.assert_not_called()


# ---------------------------------------------------------------------------
# Create 400 "already exists" hint
# ---------------------------------------------------------------------------


def test_create_400_already_exists_hint(handler, caplog):
    """A 400 with 'already exists' in the body logs an import hint."""
    handler.entity_metadata_map["entityA"]["filter_format"] = None
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"

    api_exc = type(
        "ApiException",
        (Exception,),
        {
            "status": 400,
            "reason": "BAD REQUEST",
            "body": '{"data":{"error":[{"message":"already exists with extId:abc"}]}}',
        },
    )()
    handler._execute_method_with_task_monitor = MagicMock(side_effect=api_exc)

    with (
        caplog.at_level(logging.ERROR, logger="ztf.entity_wrapper.entity_handler"),
        pytest.raises(Exception),
    ):
        handler.create("entityA", {"body": {"name": "foo"}, "resource_name": "myres"})

    assert any("ztf import" in r.message for r in caplog.records)


def test_create_400_non_duplicate_no_hint(handler, caplog):
    """A 400 without 'already exists' does NOT log the import hint."""
    handler.entity_metadata_map["entityA"]["filter_format"] = None
    handler.entity_metadata_map["entityA"]["api_instance"] = MagicMock()
    handler.entity_metadata_map["entityA"]["create_method_name"] = "create_entityA"

    api_exc = type(
        "ApiException",
        (Exception,),
        {
            "status": 400,
            "reason": "BAD REQUEST",
            "body": '{"data":{"error":[{"message":"invalid field value"}]}}',
        },
    )()
    handler._execute_method_with_task_monitor = MagicMock(side_effect=api_exc)

    with (
        caplog.at_level(logging.ERROR, logger="ztf.entity_wrapper.entity_handler"),
        pytest.raises(Exception),
    ):
        handler.create("entityA", {"body": {"name": "foo"}})

    assert not any("ztf import" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# SDK rest logger suppression
# ---------------------------------------------------------------------------


def test_sdk_rest_logger_suppressed(handler):
    """SDK package logger's stream handlers should have a filter that blocks
    rest module messages while file handlers remain unfiltered."""
    from ztf.entity_wrapper.entity_handler import _RestLogFilter

    handler._initialize_config("entityA")
    sdk_name = handler.entity_metadata_map["entityA"]["sdk_name"]
    sdk_config = handler.sdk_config_map[sdk_name]
    sdk_logger = sdk_config.logger.get("package_logger")
    assert sdk_logger is not None

    rest_prefix = f"{sdk_name}.rest"
    for h in sdk_logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(
            h, logging.FileHandler
        ):
            has_rest_filter = any(
                isinstance(f, _RestLogFilter) and f._prefix == rest_prefix
                for f in h.filters
            )
            assert has_rest_filter, "Stream handler missing _RestLogFilter"


# ---------------------------------------------------------------------------
# Custom helper read dispatch (get_entity_by_ext_id / list_entities)
# ---------------------------------------------------------------------------


@pytest.fixture
def ztf_helper_handler(global_config, monkeypatch):
    """A handler with one ``use_ztf_helper`` entity backed by a mock helper."""
    metadata = {
        "helper_entity": {
            "sdk_name": "ztf.helpers.fake_helper",
            "use_ztf_helper": True,
            "create_supported": True,
            "delete_supported": True,
            "method_params": {"create": ["body"], "delete": ["extId"]},
        },
        "task": {
            "api_class_path": "tasks_api",
            "api_instance": None,
            "sdk_name": "ntnx_prism_py_client",
            "model_class_path": "prism.v4.config.Task",
            "filter_format": "ext_id eq '{ext_id}'",
        },
        "prism_task": {
            "sdk_name": "ntnx_prism_py_client",
            "api_class_path": "tasks_api",
            "api_class_name": "TasksApi",
        },
    }
    mock_helper_instance = MagicMock()

    def fake_initialize_ztf_helper(self, entity):
        self.custom_helpers[entity] = mock_helper_instance

    monkeypatch.setattr(
        DomainEntityHandler,
        "_initialize_ztf_helper",
        fake_initialize_ztf_helper,
    )
    h = DomainEntityHandler(
        {"helper_entity"}, global_config, entity_metadata_map=metadata
    )
    return h, mock_helper_instance


def test_get_entity_by_ext_id_dispatches_to_custom_helper(ztf_helper_handler):
    """use_ztf_helper entities route get_entity_by_ext_id through the helper,
    not the SDK api_instance path (which they never populate)."""
    handler, mock_helper = ztf_helper_handler
    mock_helper.get_entity_by_ext_id.return_value = {"extId": "abc", "status": "ok"}

    result = handler.get_entity_by_ext_id("helper_entity", "abc")

    assert result == {"extId": "abc", "status": "ok"}
    mock_helper.get_entity_by_ext_id.assert_called_once_with("abc")


def test_list_entities_dispatches_to_custom_helper(ztf_helper_handler):
    """use_ztf_helper entities route list_entities through the helper."""
    handler, mock_helper = ztf_helper_handler
    mock_helper.list_entities.return_value = [{"extId": "a"}, {"extId": "b"}]

    result = handler.list_entities("helper_entity")

    assert result == [{"extId": "a"}, {"extId": "b"}]
    mock_helper.list_entities.assert_called_once_with()


def test_list_entities_forwards_filters_and_kwargs_to_custom_helper(
    ztf_helper_handler,
):
    """Helper list must receive custom_filter and leftover kwargs."""
    handler, mock_helper = ztf_helper_handler
    mock_helper.list_entities.return_value = []

    handler.list_entities(
        "helper_entity",
        _filter="name eq 'foo'",
        directory_name="corp-ad",
        _select="extId",
    )

    mock_helper.list_entities.assert_called_once_with(
        custom_filter={"directory_name": "corp-ad"},
        _filter="name eq 'foo'",
        _select="extId",
    )


def test_list_entities_forwards_explicit_custom_filter_to_helper(
    ztf_helper_handler,
):
    handler, mock_helper = ztf_helper_handler
    mock_helper.list_entities.return_value = [{"extId": "a"}]

    handler.list_entities("helper_entity", custom_filter={"directory_name": "corp-ad"})

    mock_helper.list_entities.assert_called_once_with(
        custom_filter={"directory_name": "corp-ad"}
    )


def test_list_entities_dict_filter_becomes_custom_filter(ztf_helper_handler):
    handler, mock_helper = ztf_helper_handler
    mock_helper.list_entities.return_value = []

    handler.list_entities("helper_entity", _filter={"ad_name": "corp-ad"})

    mock_helper.list_entities.assert_called_once_with(
        custom_filter={"ad_name": "corp-ad"}
    )


def test_get_with_custom_helper_raises_without_initialized_helper(
    ztf_helper_handler,
):
    """Raises a clear error rather than a KeyError when no helper is
    initialized for the entity (defensive; init should always populate it)."""
    handler, _ = ztf_helper_handler
    handler.custom_helpers.pop("helper_entity", None)

    with pytest.raises(ValueError, match="No custom helper initialized"):
        handler._get_with_custom_helper("helper_entity", "abc")


def test_list_with_custom_helper_raises_without_initialized_helper(
    ztf_helper_handler,
):
    handler, _ = ztf_helper_handler
    handler.custom_helpers.pop("helper_entity", None)

    with pytest.raises(ValueError, match="No custom helper initialized"):
        handler._list_with_custom_helper("helper_entity")


def test_sanitize_entity_data_skips_sdk_client_for_custom_helper(
    ztf_helper_handler,
):
    """Custom helpers return plain, already-JSON-safe dicts; sanitization
    must not try to look up a (nonexistent) SDK api_client for them."""
    handler, _ = ztf_helper_handler
    data = {"extId": "abc", "status": "ok"}

    result = handler.sanitize_entity_data("helper_entity", data)

    assert result == data


def test_sanitize_entity_data_custom_helper_still_rejects_falsy_data(
    ztf_helper_handler,
):
    handler, _ = ztf_helper_handler

    with pytest.raises(ValueError, match="Data is None"):
        handler.sanitize_entity_data("helper_entity", None)
