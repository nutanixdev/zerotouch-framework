"""Unit tests for ztf.repl DataNamespace, entity client, build_repl_context, and start_repl."""

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from ztf.repl import (
    DataNamespace,
    EntityHandlerProtocol,
    ReplContext,
    build_repl_context,
    start_repl,
)


def _handlers(**pairs: object) -> dict[str, EntityHandlerProtocol]:
    """Build handlers dict with cast for test doubles (structurally compatible)."""
    return cast(dict[str, EntityHandlerProtocol], pairs)


class FakeHandler:
    """Test double that records calls and returns fixed responses."""

    def __init__(self) -> None:
        """Initialize with empty call log."""
        self.calls: list[tuple[str, str, str | None, dict[str, object]]] = []

    def list_entities(
        self, entity: str, _filter: str | None = None, **kwargs: object
    ) -> list[dict[str, object]]:
        """Record list call and return fixed cluster data."""
        self.calls.append(("list", entity, _filter, dict(kwargs)))
        return [{"name": "c1"}]

    def get_entity_by_identifier(
        self, entity: str, _filter: str | None, **kwargs: object
    ) -> tuple[dict[str, object], str | None]:
        """Record get-by-filter call and return fixed entity."""
        self.calls.append(("get_by_filter", entity, _filter, dict(kwargs)))
        return {"name": "c1"}, _filter

    def get_entity_by_ext_id(
        self, entity: str, ext_id: str, **kwargs: object
    ) -> dict[str, object]:
        """Record get-by-ext-id call and return entity with extId."""
        self.calls.append(("get_by_ext_id", entity, ext_id, dict(kwargs)))
        return {"extId": ext_id}

    def sanitize_entity_data(self, entity: str, data: object) -> object:
        """Pass through data unchanged (no sanitization in tests)."""
        return data


def test_data_namespace_list_uses_default_domain() -> None:
    """List uses default_domain when only one domain is configured."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    result = data.cluster.list()
    assert result == [{"name": "c1"}]
    assert handler.calls[0][0] == "list"


def test_data_namespace_list_single_domain_no_default() -> None:
    """List uses sole handler when only one domain and default_domain is None."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain=None)
    result = data.cluster.list()
    assert result == [{"name": "c1"}]


def test_data_namespace_requires_domain_when_ambiguous() -> None:
    """List raises ValueError when multiple domains exist and no default."""
    data = DataNamespace(_handlers(lab1=FakeHandler(), lab2=FakeHandler()))
    with pytest.raises(ValueError) as exc_info:
        data.cluster.list()
    assert "domain" in str(exc_info.value)


def test_data_namespace_get_by_filter() -> None:
    """Get returns entity when filter expression is provided."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    result = data.cluster.get(filter="name eq 'c1'")
    assert result == {"name": "c1"}
    assert handler.calls[0][0] == "get_by_filter"


def test_data_namespace_get_requires_identifier() -> None:
    """Get raises ValueError when neither filter nor ext_id is provided."""
    data = DataNamespace(_handlers(lab1=FakeHandler()), default_domain="lab1")
    with pytest.raises(ValueError) as exc_info:
        data.cluster.get()
    assert "filter" in str(exc_info.value) or "ext_id" in str(exc_info.value)


def test_data_namespace_get_by_ext_id() -> None:
    """Get returns entity when ext_id is provided (ext_id branch)."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    result = data.cluster.get(ext_id="ext-123")
    assert result == {"extId": "ext-123"}
    assert handler.calls[0][0] == "get_by_ext_id"
    assert handler.calls[0][2] == "ext-123"


def test_data_namespace_get_by_ext_id_returns_none_when_not_found() -> None:
    """Get returns None when handler returns None for ext_id lookup."""

    class HandlerReturningNone(FakeHandler):
        def get_entity_by_ext_id(
            self, entity: str, ext_id: str, **kwargs: object
        ) -> dict[str, object] | None:
            return None

    data = DataNamespace(_handlers(lab1=HandlerReturningNone()), default_domain="lab1")
    result = data.cluster.get(ext_id="nonexistent")
    assert result is None


def test_data_namespace_list_with_explicit_domain() -> None:
    """List uses explicit domain when provided."""
    handler = FakeHandler()
    data = DataNamespace(
        _handlers(lab1=FakeHandler(), lab2=handler), default_domain="lab1"
    )
    result = data.cluster.list(domain="lab2")
    assert result == [{"name": "c1"}]
    assert handler.calls[0][0] == "list"


def test_data_namespace_get_with_explicit_domain() -> None:
    """Get uses explicit domain when provided."""
    handler = FakeHandler()
    data = DataNamespace(
        _handlers(lab1=FakeHandler(), lab2=handler), default_domain="lab1"
    )
    result = data.cluster.get(ext_id="e1", domain="lab2")
    assert result == {"extId": "e1"}
    assert handler.calls[0][0] == "get_by_ext_id"


def test_data_namespace_unknown_domain_raises() -> None:
    """List/get raise ValueError when domain is unknown."""
    data = DataNamespace(_handlers(lab1=FakeHandler()), default_domain="lab1")
    with pytest.raises(ValueError) as exc_info:
        data.cluster.list(domain="unknown")
    assert "Unknown domain" in str(exc_info.value)


def test_data_namespace_list_aliases_yaml_list_args() -> None:
    """List maps YAML-style filter/select/orderby/limit/page to SDK names."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    data.cluster.list(
        filter="name eq 'c1'",
        select="extId,name",
        orderby="name asc",
        limit=10,
        page=0,
        clusterExtId="cluster-1",
    )
    _op, entity, _filter, kwargs = handler.calls[0]
    assert entity == "cluster"
    assert _filter == "name eq 'c1'"
    assert kwargs["_select"] == "extId,name"
    assert kwargs["_orderby"] == "name asc"
    assert kwargs["_limit"] == 10
    assert kwargs["_page"] == 0
    assert kwargs["clusterExtId"] == "cluster-1"
    assert "orderby" not in kwargs
    assert "select" not in kwargs


def test_data_namespace_list_keeps_underscore_sdk_names() -> None:
    """List leaves already-underscored SDK kwargs unchanged."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    data.cluster.list(_filter="name eq 'c1'", _orderby="name desc", _expand="config")
    _op, _entity, _filter, kwargs = handler.calls[0]
    assert _filter == "name eq 'c1'"
    assert kwargs["_orderby"] == "name desc"
    assert kwargs["_expand"] == "config"


def test_data_namespace_get_aliases_extra_kwargs() -> None:
    """Get maps YAML-style extra kwargs before forwarding to the handler."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    data.cluster.get(filter="name eq 'c1'", orderby="name asc")
    _op, _entity, _filter, kwargs = handler.calls[0]
    assert _op == "get_by_filter"
    assert _filter == "name eq 'c1'"
    assert kwargs["_orderby"] == "name asc"


def test_data_namespace_calls_ensure_entity_when_present() -> None:
    """List lazily initializes entity types the handler has not loaded yet."""

    class EnsuringHandler(FakeHandler):
        def ensure_entity(self, entity: str) -> None:
            self.calls.append(("ensure", entity, None, {}))

    handler = EnsuringHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    data.vm.list()
    assert handler.calls[0] == ("ensure", "vm", None, {})
    assert handler.calls[1][0] == "list"
    assert handler.calls[1][1] == "vm"


def test_data_namespace_dir_includes_entity_names() -> None:
    """dir(data) includes registered entity types for tab completion."""
    data = DataNamespace(_handlers(lab1=FakeHandler()), default_domain="lab1")
    names = dir(data)
    assert "cluster" in names
    assert "vm" in names


def test_repl_context_to_locals() -> None:
    """ReplContext.to_locals returns ctx and data."""
    handler = FakeHandler()
    data = DataNamespace(_handlers(lab1=handler), default_domain="lab1")
    ctx = ReplContext(
        global_config={},
        config={},
        handlers={},
        data=data,
        default_domain="lab1",
    )
    locals_dict = ctx.to_locals()
    assert "ctx" in locals_dict
    assert "data" in locals_dict
    assert locals_dict["ctx"] is ctx
    assert locals_dict["data"] is data


# ---------------------------------------------------------------------------
# build_repl_context
# ---------------------------------------------------------------------------

_MINIMAL_ENTITY_MAP = {
    "cluster": {
        "sdk_name": "ntnx_clustermgmt_py_client",
        "api_class_path": "clusters_api",
        "model_class_path": "Cluster",
        "create_method_name": "create_cluster",
        "get_method_name": "get_cluster_by_id",
        "update_method_name": "update_cluster_by_id",
        "delete_method_name": "delete_cluster_by_id",
        "list_method_name": "list_clusters",
        "operations": [],
        "filter_format": "name eq '{name}'",
        "update_supported": True,
        "namespace": "clustermgmt",
        "etag_required": {"update": False, "delete": False},
        "method_params": {
            "create": ["body"],
            "get": ["extId"],
            "update": ["extId", "body"],
            "delete": ["extId"],
        },
    },
}


def test_build_repl_context_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_repl_context returns ReplContext with handlers and data namespace."""
    monkeypatch.setattr(
        "ztf.repl.entity_metadata_map",
        _MINIMAL_ENTITY_MAP,
    )
    global_config = {"config": {"debug": False}}
    config = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "resources": {"cluster": {"c1": {"body": {"name": "c1"}}}},
            }
        }
    }
    with patch("ztf.repl.DomainEntityHandler") as mock_handler_cls:
        ctx = build_repl_context(global_config, config)
        mock_handler_cls.assert_called()
    assert isinstance(ctx, ReplContext)
    assert ctx.global_config == global_config
    assert ctx.config == config
    assert ctx.default_domain == "lab1"
    assert ctx.data.cluster is not None


def test_build_repl_context_domains_not_dict() -> None:
    """build_repl_context raises ValueError when domains is not a dict."""
    with pytest.raises(ValueError) as exc_info:
        build_repl_context({}, {"domains": "invalid"})
    assert "domains" in str(exc_info.value) and "dict" in str(exc_info.value)


def test_build_repl_context_empty_domains() -> None:
    """build_repl_context raises ValueError when domains is empty."""
    with pytest.raises(ValueError) as exc_info:
        build_repl_context({}, {"domains": {}})
    assert "at least one domain" in str(exc_info.value)


def test_build_repl_context_missing_credentials() -> None:
    """build_repl_context raises ValueError when domain lacks username/password."""
    config = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "",
                "password": "pass",
                "resources": {"cluster": {}},
            }
        }
    }
    with pytest.raises(ValueError) as exc_info:
        build_repl_context({}, config)
    assert "username" in str(exc_info.value) or "password" in str(exc_info.value)


def test_build_repl_context_no_resources_or_data() -> None:
    """build_repl_context raises ValueError when no domain has resources or data."""
    config = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
            }
        }
    }
    with pytest.raises(ValueError) as exc_info:
        build_repl_context({}, config)
    assert "resources" in str(exc_info.value) or "data" in str(exc_info.value)


def test_build_repl_context_uses_data_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_repl_context uses data sources when resources are missing."""
    monkeypatch.setattr(
        "ztf.repl.entity_metadata_map",
        _MINIMAL_ENTITY_MAP,
    )
    global_config = {"config": {"debug": False}}
    config = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "data": {"cluster": {"c1": {"filter": "name eq 'c1'"}}},
            }
        }
    }
    with patch("ztf.repl.DomainEntityHandler") as mock_handler_cls:
        ctx = build_repl_context(global_config, config)
        mock_handler_cls.assert_called()
    assert isinstance(ctx, ReplContext)
    assert ctx.default_domain == "lab1"


def test_build_repl_context_shared_host_reuses_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_repl_context reuses handler when multiple domains share a host."""
    monkeypatch.setattr(
        "ztf.repl.entity_metadata_map",
        _MINIMAL_ENTITY_MAP,
    )
    global_config = {"config": {"debug": False}}
    config = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "resources": {"cluster": {"c1": {"body": {"name": "c1"}}}},
            },
            "lab2": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "resources": {"cluster": {"c2": {"body": {"name": "c2"}}}},
            },
        }
    }
    with patch("ztf.repl.DomainEntityHandler") as mock_handler_cls:
        ctx = build_repl_context(global_config, config)
        assert mock_handler_cls.call_count == 1
    assert ctx.handlers["lab1"] is ctx.handlers["lab2"]


# ---------------------------------------------------------------------------
# start_repl
# ---------------------------------------------------------------------------


def test_start_repl_exec_code() -> None:
    """start_repl executes exec_code with locals."""
    locals_dict: dict[str, object] = {"value": 0}
    start_repl(locals_dict, exec_code="value = 42")
    assert locals_dict["value"] == 42


def test_start_repl_script_path(tmp_path: Path) -> None:
    """start_repl executes script file when script_path is provided."""
    script_path = tmp_path / "script.py"
    script_path.write_text("value = 99")
    locals_dict: dict[str, object] = {"value": 0}
    start_repl(locals_dict, script_path=str(script_path))
    assert locals_dict["value"] == 99


def test_start_repl_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_repl falls back to interactive mode when no exec/script."""
    called = {"value": False}

    def fake_interact(*_args: object, **_kwargs: object) -> None:
        called["value"] = True

    monkeypatch.setattr("ztf.repl.code.interact", fake_interact)
    start_repl({"value": 1})
    assert called["value"] is True
