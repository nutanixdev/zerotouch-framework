"""Tests for ``ztf.sdk_utils``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ztf.sdk_utils import call_api_with_body, deep_merge, dict_to_sdk_model

# ---------------------------------------------------------------------------
# dict_to_sdk_model
# ---------------------------------------------------------------------------


class TestDictToSdkModel:
    def _make_method(self, docstring: str) -> MagicMock:
        m = MagicMock()
        m.__doc__ = docstring
        return m

    def test_no_docstring_match(self) -> None:
        method = self._make_method("No relevant info here.")
        result = dict_to_sdk_model(method, {"a": 1}, MagicMock())
        assert result == {"a": 1}

    def test_none_docstring(self) -> None:
        method = MagicMock()
        method.__doc__ = None
        result = dict_to_sdk_model(method, {"a": 1}, MagicMock())
        assert result == {"a": 1}

    def test_model_class_not_found(self) -> None:
        doc = ":type body: :class:`~ntnx_fake_py_client.models.foo.bar.Missing`"
        method = self._make_method(doc)
        mock_sdk = MagicMock()
        mock_sdk.Missing = None
        delattr(mock_sdk, "Missing")
        with patch("importlib.import_module", return_value=mock_sdk):
            result = dict_to_sdk_model(method, {"a": 1}, MagicMock())
        assert result == {"a": 1}

    def test_model_no_swagger_types(self) -> None:
        doc = ":type body: :class:`~ntnx_fake_py_client.models.foo.MyModel`"
        method = self._make_method(doc)
        model_cls = MagicMock()
        del model_cls.swagger_types
        mock_sdk = MagicMock()
        mock_sdk.MyModel = model_cls
        with patch("importlib.import_module", return_value=mock_sdk):
            result = dict_to_sdk_model(method, {"a": 1}, MagicMock())
        assert result is not None

    def test_with_swagger_types(self) -> None:
        doc = ":type body: :class:`~ntnx_test_py_client.models.v4.config.Widget`"
        method = self._make_method(doc)

        model_cls = MagicMock()
        model_cls.swagger_types = {"name": "str", "count": "int"}
        model_cls.attribute_map = {"name": "name", "count": "count"}

        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data

        mock_sdk = MagicMock()
        mock_sdk.Widget = model_cls
        with patch("importlib.import_module", return_value=mock_sdk):
            dict_to_sdk_model(method, {"name": "foo", "count": 5}, client)
        model_cls.assert_called_once()

    def test_with_nested_object_type(self) -> None:
        doc = ":type body: :class:`~ntnx_test_py_client.models.v4.config.Widget`"
        method = self._make_method(doc)

        nested_cls = MagicMock()
        nested_cls.swagger_types = {"ip": "str"}
        nested_cls.attribute_map = {"ip": "ip"}

        model_cls = MagicMock()
        model_cls.swagger_types = {"target": "OneOfTarget"}
        model_cls.attribute_map = {"target": "target"}

        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data

        mock_sdk = MagicMock()
        mock_sdk.Widget = model_cls
        mock_sdk.IpTarget = nested_cls
        with patch("importlib.import_module", return_value=mock_sdk):
            body = {
                "target": {
                    "$objectType": "v4.config.IpTarget",
                    "ip": "1.2.3.4",
                }
            }
            dict_to_sdk_model(method, body, client)
        model_cls.assert_called_once()

    def test_import_error_returns_dict(self) -> None:
        doc = ":type body: :class:`~ntnx_missing_py_client.models.v4.Foo`"
        method = self._make_method(doc)
        with patch("importlib.import_module", side_effect=ImportError("nope")):
            result = dict_to_sdk_model(method, {"a": 1}, MagicMock())
        assert result == {"a": 1}

    def test_none_value_skipped(self) -> None:
        doc = ":type body: :class:`~ntnx_test_py_client.models.v4.config.Widget`"
        method = self._make_method(doc)
        model_cls = MagicMock()
        model_cls.swagger_types = {"name": "str", "optional": "str"}
        model_cls.attribute_map = {"name": "name", "optional": "optional"}
        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data
        mock_sdk = MagicMock()
        mock_sdk.Widget = model_cls
        with patch("importlib.import_module", return_value=mock_sdk):
            dict_to_sdk_model(method, {"name": "foo"}, client)
        call_kwargs = model_cls.call_args[1]
        assert "optional" not in call_kwargs

    @pytest.mark.parametrize(
        "falsy_value",
        [False, 0, 0.0, "", [], {}],
        ids=[
            "false",
            "zero_int",
            "zero_float",
            "empty_str",
            "empty_list",
            "empty_dict",
        ],
    )
    def test_preserves_legitimate_falsy_values(self, falsy_value: object) -> None:
        """Regression: ``body_dict.get(attr) or body_dict.get(camel_key)``
        silently replaced legitimate falsy user values (``False``, ``0``,
        ``""``, ``[]``, ``{}``) with ``None`` and fell through to the SDK
        default.  Phase A replaces the ``or`` coalesce with explicit
        membership checks."""
        doc = ":type body: :class:`~ntnx_test_py_client.models.v4.config.Widget`"
        method = self._make_method(doc)
        model_cls = MagicMock()
        model_cls.swagger_types = {"flag": "bool"}
        model_cls.attribute_map = {"flag": "flag"}
        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data
        mock_sdk = MagicMock()
        mock_sdk.Widget = model_cls

        with patch("importlib.import_module", return_value=mock_sdk):
            dict_to_sdk_model(method, {"flag": falsy_value}, client)

        call_kwargs = model_cls.call_args[1]
        assert "flag" in call_kwargs
        assert call_kwargs["flag"] == falsy_value

    def test_camel_case_fallback_still_works(self) -> None:
        """snake_case→camelCase fallback must still resolve when only the
        camelCase key is present (no regression from the falsy-safe fix)."""
        doc = ":type body: :class:`~ntnx_test_py_client.models.v4.config.Widget`"
        method = self._make_method(doc)
        model_cls = MagicMock()
        model_cls.swagger_types = {"is_enabled": "bool"}
        model_cls.attribute_map = {"is_enabled": "isEnabled"}
        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data
        mock_sdk = MagicMock()
        mock_sdk.Widget = model_cls

        with patch("importlib.import_module", return_value=mock_sdk):
            dict_to_sdk_model(method, {"isEnabled": False}, client)

        call_kwargs = model_cls.call_args[1]
        assert call_kwargs["is_enabled"] is False


# ---------------------------------------------------------------------------
# Model resolution against a generated-SDK-shaped package
# ---------------------------------------------------------------------------


def _make_model(name: str, swagger_types: dict, attribute_map: dict, marker: str):
    """Build a stand-in for a generated SDK model class."""

    def init(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    return type(
        name,
        (),
        {
            "swagger_types": swagger_types,
            "attribute_map": attribute_map,
            "marker": marker,
            "__init__": init,
        },
    )


@pytest.fixture
def fake_sdk():
    """Register a package laid out the way the ntnx clients are.

    Generated models live at ``<sdk>.models.<dotted.type.path>`` with the
    class named after the final segment, and colliding bare class names are
    re-exported at the top level under disambiguated aliases.  Reproducing
    that shape is what lets these tests reach the submodule-import path in
    ``_resolve_model_class``; the ``MagicMock``-based tests above cannot,
    because ``MagicMock`` has no ``__name__``.
    """
    import sys
    import types

    sdk_name = "ntnx_fake_py_client"
    inner = _make_model(
        "Inner",
        {"mac_address": "list[str]", "label": "str"},
        {"mac_address": "macAddress", "label": "label"},
        marker="pkg-inner",
    )
    # Same bare class name in a second namespace, as with lifecycle's and
    # common's BasicAuth.  Only the dotted path tells them apart.
    other_inner = _make_model("Inner", {"label": "str"}, {"label": "label"}, "other")
    outer = _make_model(
        "Outer",
        {
            "inner": "pkg.v4.config.Inner",
            "items": "list[pkg.v4.config.Inner]",
            "name": "str",
        },
        {"inner": "inner", "items": "items", "name": "name"},
        marker="outer",
    )

    modules: dict[str, types.ModuleType] = {}
    for path in [
        sdk_name,
        f"{sdk_name}.models",
        f"{sdk_name}.models.pkg",
        f"{sdk_name}.models.pkg.v4",
        f"{sdk_name}.models.pkg.v4.config",
        f"{sdk_name}.models.other",
        f"{sdk_name}.models.other.v1",
        f"{sdk_name}.models.other.v1.config",
    ]:
        mod = types.ModuleType(path)
        mod.__path__ = []
        modules[path] = mod
    for path, cls in [
        (f"{sdk_name}.models.pkg.v4.config.Inner", inner),
        (f"{sdk_name}.models.pkg.v4.config.Outer", outer),
        (f"{sdk_name}.models.other.v1.config.Inner", other_inner),
    ]:
        mod = types.ModuleType(path)
        setattr(mod, cls.__name__, cls)
        modules[path] = mod

    # The top-level bare name deliberately points at the *wrong* class, so
    # any test that passes proves resolution went through the submodule.
    modules[sdk_name].Inner = other_inner
    modules[sdk_name].Outer = outer

    saved = {k: sys.modules.get(k) for k in modules}
    sys.modules.update(modules)
    try:
        yield types.SimpleNamespace(
            name=sdk_name, inner=inner, other_inner=other_inner, outer=outer
        )
    finally:
        for key, value in saved.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


class TestResolveModelClass:
    def test_dotted_path_resolves_via_submodule_not_bare_name(self, fake_sdk) -> None:
        """The bare class name is ambiguous across namespaces, so resolution
        must go through the exact submodule path."""
        import sys

        from ztf.sdk_utils import _resolve_model_class

        sdk = sys.modules[fake_sdk.name]
        assert _resolve_model_class("pkg.v4.config.Inner", sdk) is fake_sdk.inner
        assert (
            _resolve_model_class("other.v1.config.Inner", sdk) is fake_sdk.other_inner
        )

    def test_unimportable_path_falls_back_to_top_level(self, fake_sdk) -> None:
        import sys

        from ztf.sdk_utils import _resolve_model_class

        sdk = sys.modules[fake_sdk.name]
        assert _resolve_model_class("nope.v9.Outer", sdk) is fake_sdk.outer

    def test_unknown_class_resolves_to_none(self, fake_sdk) -> None:
        import sys

        from ztf.sdk_utils import _resolve_model_class

        sdk = sys.modules[fake_sdk.name]
        assert _resolve_model_class("nope.v9.NoSuchModel", sdk) is None

    def test_sdk_without_name_uses_top_level_only(self) -> None:
        from ztf.sdk_utils import _resolve_model_class

        sdk = MagicMock()
        del sdk.__name__
        assert _resolve_model_class("a.b.Widget", sdk) is sdk.Widget


class TestNestedConversion:
    def _method(self) -> MagicMock:
        m = MagicMock()
        m.__doc__ = (
            ":type body: :class:`~ntnx_fake_py_client.models.pkg.v4.config.Outer`"
        )
        return m

    def _client(self) -> MagicMock:
        client = MagicMock()
        client.deserialize.side_effect = lambda klass, data: data
        return client

    def test_concrete_nested_model_is_built(self, fake_sdk) -> None:
        """A dict under a concrete dotted attr_type becomes that model,
        with its own nested fields converted rather than flattened."""
        result = dict_to_sdk_model(
            self._method(),
            {"inner": {"macAddress": ["eth0"], "label": "n1"}},
            self._client(),
        )
        assert isinstance(result, fake_sdk.outer)
        assert isinstance(result.inner, fake_sdk.inner)
        assert result.inner.mac_address == ["eth0"]
        assert result.inner.label == "n1"

    def test_list_elements_are_converted_individually(self, fake_sdk) -> None:
        result = dict_to_sdk_model(
            self._method(),
            {"items": [{"label": "a"}, {"label": "b"}]},
            self._client(),
        )
        assert [type(i) for i in result.items] == [fake_sdk.inner, fake_sdk.inner]
        assert [i.label for i in result.items] == ["a", "b"]

    def test_object_type_discriminator_overrides_declared_type(self, fake_sdk) -> None:
        """oneOf fields name their concrete class inline; that must win over
        whatever the attribute declares."""
        result = dict_to_sdk_model(
            self._method(),
            {"inner": {"$objectType": "other.v1.config.Inner", "label": "x"}},
            self._client(),
        )
        assert isinstance(result.inner, fake_sdk.other_inner)

    def test_explicit_none_nested_value_is_dropped(self, fake_sdk) -> None:
        result = dict_to_sdk_model(
            self._method(), {"inner": None, "name": "keep"}, self._client()
        )
        assert not hasattr(result, "inner")
        assert result.name == "keep"

    def test_primitive_attr_types_bypass_model_resolution(self, fake_sdk) -> None:
        """'str' has no dot, so it must never be probed as a model path."""
        from ztf.sdk_utils import _resolve_model_class

        with patch("ztf.sdk_utils._resolve_model_class") as resolve:
            resolve.side_effect = _resolve_model_class
            dict_to_sdk_model(self._method(), {"name": "plain"}, self._client())
        # Only the body model itself is resolved; the 'str' field is not.
        assert [c.args[0] for c in resolve.call_args_list] == ["pkg.v4.config.Outer"]


# ---------------------------------------------------------------------------
# call_api_with_body
# ---------------------------------------------------------------------------


class TestCallApiWithBody:
    def test_success_with_dict(self) -> None:
        api_method = MagicMock(return_value="ok")
        result = call_api_with_body(api_method, {"a": 1}, MagicMock())
        assert result == "ok"
        api_method.assert_called_once_with(body={"a": 1})

    @patch("ztf.sdk_utils.dict_to_sdk_model")
    def test_proactive_model_conversion(self, mock_convert: MagicMock) -> None:
        model_obj = MagicMock(name="SdkModel")
        mock_convert.return_value = model_obj
        api_method = MagicMock(return_value="ok")
        client = MagicMock()

        result = call_api_with_body(api_method, {"a": 1}, client)

        mock_convert.assert_called_once_with(api_method, {"a": 1}, client)
        api_method.assert_called_once_with(body=model_obj)
        assert result == "ok"

    def test_dict_rejection_propagates(self) -> None:
        api_method = MagicMock()
        api_method.__doc__ = "no match"
        api_method.side_effect = Exception("unsupported object type dict")
        with pytest.raises(Exception, match="unsupported object type dict"):
            call_api_with_body(api_method, {"a": 1}, MagicMock())

    def test_non_matching_error_reraise(self) -> None:
        api_method = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            call_api_with_body(api_method, {"a": 1}, MagicMock())

    def test_with_extra_kwargs(self) -> None:
        api_method = MagicMock(return_value="ok")
        call_api_with_body(api_method, {"a": 1}, MagicMock(), extId="abc")
        api_method.assert_called_once_with(body={"a": 1}, extId="abc")


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_flat_merge(self) -> None:
        base = {"a": 1, "b": 2}
        result = deep_merge(base, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        base = {"config": {"host": "a", "port": 80}}
        result = deep_merge(base, {"config": {"port": 443}})
        assert result == {"config": {"host": "a", "port": 443}}

    def test_none_skipped(self) -> None:
        base = {"a": 1}
        result = deep_merge(base, {"a": None, "b": None})
        assert result == {"a": 1}

    def test_overwrites_non_dict(self) -> None:
        base = {"a": "old"}
        result = deep_merge(base, {"a": "new"})
        assert result == {"a": "new"}

    def test_empty_update(self) -> None:
        base = {"a": 1}
        result = deep_merge(base, {})
        assert result == {"a": 1}

    def test_returns_base(self) -> None:
        base = {"a": 1}
        result = deep_merge(base, {"b": 2})
        assert result is base
