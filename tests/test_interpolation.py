"""Tests for ztf.config.interpolation."""

from pathlib import Path

import pytest

from ztf.config.interpolation import (
    InterpolationContext,
    _iter_tokens,
    _split_fn_args,
    classify_unresolved_tokens,
    extract_data_source_refs,
    extract_indexed_source_tokens,
    extract_resource_refs,
    has_tokens,
    resolve,
    set_template_root,
    validate_data_tokens,
)


@pytest.fixture
def template_root(tmp_path: Path) -> Path:
    """Sandbox ``{fn.template(...)}`` to ``tmp_path`` for the test."""
    import ztf.config.interpolation as interp

    previous = interp._TEMPLATE_ROOT
    set_template_root(tmp_path)
    try:
        yield tmp_path
    finally:
        interp._TEMPLATE_ROOT = previous


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_ctx() -> InterpolationContext:
    """Context with variables and a single resource."""
    return InterpolationContext(
        variables={"env": "prod", "cluster_vip": "10.10.0.99"},
        resource_state={
            "prod-cluster": {"ext_id": "abc-123", "body": {"name": "falki-03"}},
        },
    )


@pytest.fixture
def data_ctx() -> InterpolationContext:
    """Context with data cache."""
    return InterpolationContext(
        variables={"env": "prod"},
        data_cache={
            "cluster": {
                "existing-cluster": {
                    "data": [{"extId": "xyz-789", "name": "jetson-cluster"}],
                    "metadata": {"totalAvailableResults": 1},
                },
            },
            "category": {
                "env-tag": {
                    "data": [{"extId": "cat-001"}],
                    "metadata": {"totalAvailableResults": 1},
                },
            },
        },
    )


@pytest.fixture
def cross_domain_ctx() -> InterpolationContext:
    """Context with cross-domain resource state."""
    return InterpolationContext(
        variables={},
        resource_state={
            "local-res": {"ext_id": "local-111"},
        },
        domain_states={
            "lab2": {
                "remote-cluster": {"ext_id": "remote-222", "body": {"name": "rc"}},
            },
        },
    )


@pytest.fixture
def for_each_ctx() -> InterpolationContext:
    """Context with for_each data."""
    return InterpolationContext(
        variables={"env": "prod"},
        for_each={
            "key": "analytics",
            "value": {"name": "analytics-container", "replication": 3},
        },
    )


# ---------------------------------------------------------------------------
# Variable resolution
# ---------------------------------------------------------------------------


class TestVariableResolution:
    def test_simple_var(self, basic_ctx: InterpolationContext) -> None:
        assert resolve("{var.env}", basic_ctx) == "prod"

    def test_var_in_string(self, basic_ctx: InterpolationContext) -> None:
        result = resolve("{var.env}-storage-container", basic_ctx)
        assert result == "prod-storage-container"

    def test_missing_var_lenient(self, basic_ctx: InterpolationContext) -> None:
        result = resolve("{var.missing}", basic_ctx)
        assert result == "{var.missing}"

    def test_missing_var_strict(self, basic_ctx: InterpolationContext) -> None:
        with pytest.raises(ValueError, match="Unresolved"):
            resolve("{var.missing}", basic_ctx, strict=True)

    def test_var_preserves_type(self) -> None:
        ctx = InterpolationContext(variables={"port": 514})
        result = resolve("{var.port}", ctx)
        assert result == 514
        assert isinstance(result, int)

    def test_var_in_embedded_string_becomes_str(self) -> None:
        ctx = InterpolationContext(variables={"port": 514})
        result = resolve("port:{var.port}", ctx)
        assert result == "port:514"


# ---------------------------------------------------------------------------
# Resource references
# ---------------------------------------------------------------------------


class TestResourceResolution:
    def test_ext_id(self, basic_ctx: InterpolationContext) -> None:
        assert resolve("{prod-cluster.ext_id}", basic_ctx) == "abc-123"

    def test_body_field(self, basic_ctx: InterpolationContext) -> None:
        assert resolve("{prod-cluster.body.name}", basic_ctx) == "falki-03"

    def test_missing_resource(self, basic_ctx: InterpolationContext) -> None:
        result = resolve("{unknown-res.ext_id}", basic_ctx)
        assert result == "{unknown-res.ext_id}"


# ---------------------------------------------------------------------------
# Data source references
# ---------------------------------------------------------------------------


class TestDataResolution:
    def test_ext_id(self, data_ctx: InterpolationContext) -> None:
        assert (
            resolve("{data.cluster.existing-cluster.data.0.extId}", data_ctx)
            == "xyz-789"
        )

    def test_name_field(self, data_ctx: InterpolationContext) -> None:
        assert (
            resolve("{data.cluster.existing-cluster.data.0.name}", data_ctx)
            == "jetson-cluster"
        )

    def test_metadata_total_results(self, data_ctx: InterpolationContext) -> None:
        assert (
            resolve(
                "{data.cluster.existing-cluster.metadata.totalAvailableResults}",
                data_ctx,
            )
            == 1
        )

    def test_missing_source(self, data_ctx: InterpolationContext) -> None:
        result = resolve("{data.cluster.nonexistent.data.0.extId}", data_ctx)
        assert result == "{data.cluster.nonexistent.data.0.extId}"

    def test_domain_scoped_data(self) -> None:
        ctx = InterpolationContext(
            data_cache={
                "lab1": {
                    "cluster": {
                        "all": {
                            "data": [{"extId": "lab-111"}],
                            "metadata": {"totalAvailableResults": 1},
                        }
                    }
                }
            }
        )
        assert resolve("{data.lab1.cluster.all.data.0.extId}", ctx) == "lab-111"

    def test_flat_cache_short_token(self) -> None:
        """Flat ``{entity: {source: ...}}`` shape + 4-part token (no domain)."""
        ctx = InterpolationContext(
            data_cache={
                "cluster": {
                    "mine": {"data": [{"extId": "flat-222"}]},
                }
            }
        )
        assert resolve("{data.cluster.mine.data.0.extId}", ctx) == "flat-222"

    def test_domain_scoped_falls_back_when_mismatch(self) -> None:
        """A 5-part token on a flat cache must fall back to the flat shape.

        Regression for 4.2: the lookup helper should not incorrectly
        classify the token as domain-scoped when ``parts[1]`` does not
        actually name a domain in the cache.
        """
        ctx = InterpolationContext(
            data_cache={
                "cluster": {
                    "mine": {"data": {"nested": {"field": "ok"}}},
                }
            }
        )
        assert resolve("{data.cluster.mine.data.nested.field}", ctx) == "ok"

    def test_domain_scoped_entity_not_in_domain(self) -> None:
        """Domain exists but the entity key does not — must return unresolved."""
        ctx = InterpolationContext(
            data_cache={"lab1": {"cluster": {"all": {"data": []}}}},
        )
        token = "{data.lab1.missing-entity.foo.bar.baz}"
        assert resolve(token, ctx) == token


# ---------------------------------------------------------------------------
# Cross-domain references
# ---------------------------------------------------------------------------


class TestCrossDomainResolution:
    def test_cross_domain_ext_id(self, cross_domain_ctx: InterpolationContext) -> None:
        assert resolve("{lab2.remote-cluster.ext_id}", cross_domain_ctx) == "remote-222"

    def test_cross_domain_body_field(
        self, cross_domain_ctx: InterpolationContext
    ) -> None:
        assert resolve("{lab2.remote-cluster.body.name}", cross_domain_ctx) == "rc"

    def test_local_resource_not_confused(
        self, cross_domain_ctx: InterpolationContext
    ) -> None:
        assert resolve("{local-res.ext_id}", cross_domain_ctx) == "local-111"

    def test_same_domain_resource_named_like_a_domain_falls_through(self) -> None:
        """A resource named the same as a real domain must still be
        reachable via {resource_name.field} -- the cross-domain branch
        should fall through to the same-domain lookup instead of
        shadowing it just because parts[0] also happens to name a domain.
        """
        ctx = InterpolationContext(
            resource_state={
                "lab2": {"ext_id": "local-999", "body": {"name": "myres"}},
            },
            domain_states={
                "lab2": {"other-resource": {"ext_id": "remote-1"}},
            },
        )
        assert resolve("{lab2.body.name}", ctx) == "myres"
        assert resolve("{lab2.ext_id}", ctx) == "local-999"

    def test_cross_domain_still_wins_when_resource_exists_there(self) -> None:
        """When the referenced resource *does* exist in the named domain,
        the cross-domain interpretation still takes priority."""
        ctx = InterpolationContext(
            resource_state={"lab2": {"ext_id": "local-999"}},
            domain_states={
                "lab2": {"lab2": {"ext_id": "remote-1"}},
            },
        )
        assert resolve("{lab2.lab2.ext_id}", ctx) == "remote-1"


# ---------------------------------------------------------------------------
# for_each
# ---------------------------------------------------------------------------


class TestForEachResolution:
    def test_each_key(self, for_each_ctx: InterpolationContext) -> None:
        assert resolve("{each.key}", for_each_ctx) == "analytics"

    def test_each_value_field(self, for_each_ctx: InterpolationContext) -> None:
        assert resolve("{each.value.name}", for_each_ctx) == "analytics-container"

    def test_each_value_int(self, for_each_ctx: InterpolationContext) -> None:
        result = resolve("{each.value.replication}", for_each_ctx)
        assert result == 3

    def test_each_key_in_string(self, for_each_ctx: InterpolationContext) -> None:
        result = resolve("{each.key}-sc", for_each_ctx)
        assert result == "analytics-sc"


# ---------------------------------------------------------------------------
# Recursive resolution
# ---------------------------------------------------------------------------


class TestRecursiveResolution:
    def test_dict(self, basic_ctx: InterpolationContext) -> None:
        data = {
            "name": "{var.env}-cluster",
            "vip": "{var.cluster_vip}",
            "ref": "{prod-cluster.ext_id}",
        }
        result = resolve(data, basic_ctx)
        assert result == {
            "name": "prod-cluster",
            "vip": "10.10.0.99",
            "ref": "abc-123",
        }

    def test_list(self, basic_ctx: InterpolationContext) -> None:
        data = ["{var.env}", "{prod-cluster.ext_id}"]
        result = resolve(data, basic_ctx)
        assert result == ["prod", "abc-123"]

    def test_nested(self, basic_ctx: InterpolationContext) -> None:
        data = {"outer": {"inner": "{var.env}"}}
        result = resolve(data, basic_ctx)
        assert result == {"outer": {"inner": "prod"}}

    def test_passthrough_primitives(self, basic_ctx: InterpolationContext) -> None:
        assert resolve(42, basic_ctx) == 42
        assert resolve(True, basic_ctx) is True
        assert resolve(None, basic_ctx) is None

    def test_no_mutation(self, basic_ctx: InterpolationContext) -> None:
        original = {"name": "{var.env}"}
        _ = resolve(original, basic_ctx)
        assert original == {"name": "{var.env}"}


# ---------------------------------------------------------------------------
# has_tokens
# ---------------------------------------------------------------------------


class TestHasTokens:
    def test_string_with_token(self) -> None:
        assert has_tokens("{var.env}") is True

    def test_string_without_token(self) -> None:
        assert has_tokens("plain text") is False

    def test_dict_with_token(self) -> None:
        assert has_tokens({"k": "{var.x}"}) is True

    def test_list_with_token(self) -> None:
        assert has_tokens(["a", "{var.x}"]) is True

    def test_empty_structures(self) -> None:
        assert has_tokens({}) is False
        assert has_tokens([]) is False

    def test_number(self) -> None:
        assert has_tokens(42) is False


# ---------------------------------------------------------------------------
# Edge cases for uncovered lines
# ---------------------------------------------------------------------------


class TestWalkPathEdges:
    """Cover _walk_path branches: missing key (L85) and non-dict value (L87)."""

    def test_missing_nested_key(self, basic_ctx: InterpolationContext) -> None:
        """Body exists but field inside body is absent -> _UNRESOLVED path."""
        result = resolve("{prod-cluster.body.nonexistent}", basic_ctx)
        assert result == "{prod-cluster.body.nonexistent}"

    def test_non_dict_intermediate(self, basic_ctx: InterpolationContext) -> None:
        """ext_id is a string, drilling deeper hits the non-dict branch."""
        result = resolve("{prod-cluster.ext_id.deeper}", basic_ctx)
        assert result == "{prod-cluster.ext_id.deeper}"


class TestForEachEdgeCases:
    """Cover each.value missing (L113) and each.<unknown> (L115)."""

    def test_each_value_missing(self) -> None:
        ctx = InterpolationContext(for_each={"key": "k"})
        result = resolve("{each.value}", ctx)
        assert result == "{each.value}"

    def test_each_unknown_subfield(self) -> None:
        ctx = InterpolationContext(for_each={"key": "k", "value": "v"})
        result = resolve("{each.other}", ctx)
        assert result == "{each.other}"


class TestCrossDomainMissingResource:
    """Cover cross-domain resource is None (L134)."""

    def test_missing_resource_in_known_domain(
        self, cross_domain_ctx: InterpolationContext
    ) -> None:
        result = resolve("{lab2.nonexistent.ext_id}", cross_domain_ctx)
        assert result == "{lab2.nonexistent.ext_id}"


class TestSinglePartTokenFallthrough:
    """Cover the final return _UNRESOLVED (L148) -- single-part token."""

    def test_bare_token(self) -> None:
        ctx = InterpolationContext()
        result = resolve("{something}", ctx)
        assert result == "{something}"


class TestEmbeddedTokenStrictUnresolved:
    """Cover strict raise inside the embedded-token replacer (L192-196)."""

    def test_strict_embedded_unresolved(self) -> None:
        ctx = InterpolationContext(variables={"env": "prod"})
        with pytest.raises(ValueError, match="Unresolved"):
            resolve("prefix-{var.missing}-suffix", ctx, strict=True)

    def test_lenient_embedded_unresolved(self) -> None:
        ctx = InterpolationContext(variables={"env": "prod"})
        result = resolve("prefix-{var.missing}-suffix", ctx)
        assert result == "prefix-{var.missing}-suffix"


# ---------------------------------------------------------------------------
# extract_resource_refs
# ---------------------------------------------------------------------------


class TestExtractResourceRefs:
    """Tests for extract_resource_refs()."""

    def test_simple_ref(self) -> None:
        known = {"my_cat", "my_vm"}
        data = "{my_cat.ext_id}"
        assert extract_resource_refs(data, known) == {"my_cat"}

    def test_multiple_refs(self) -> None:
        known = {"res_a", "res_b", "res_c"}
        data = "prefix-{res_a.ext_id}-{res_b.body.name}"
        assert extract_resource_refs(data, known) == {"res_a", "res_b"}

    def test_var_skipped(self) -> None:
        known = {"my_res"}
        data = "{var.env}"
        assert extract_resource_refs(data, known) == set()

    def test_each_skipped(self) -> None:
        known = {"my_res"}
        data = "{each.key}"
        assert extract_resource_refs(data, known) == set()

    def test_data_skipped(self) -> None:
        known = {"cluster"}
        data = "{data.cluster.grove.ext_id}"
        assert extract_resource_refs(data, known) == set()

    def test_unknown_resource_skipped(self) -> None:
        known = {"res_a"}
        data = "{unknown.ext_id}"
        assert extract_resource_refs(data, known) == set()

    def test_nested_dict(self) -> None:
        known = {"res_a", "res_b"}
        data = {"outer": {"inner": "{res_a.ext_id}"}, "other": "{res_b.body.x}"}
        assert extract_resource_refs(data, known) == {"res_a", "res_b"}

    def test_nested_list(self) -> None:
        known = {"res_a"}
        data = ["{res_a.ext_id}", "plain", 42]
        assert extract_resource_refs(data, known) == {"res_a"}

    def test_no_tokens(self) -> None:
        known = {"res_a"}
        assert extract_resource_refs("plain string", known) == set()
        assert extract_resource_refs(42, known) == set()
        assert extract_resource_refs(None, known) == set()

    def test_single_part_token_skipped(self) -> None:
        known = {"single"}
        data = "{single}"
        assert extract_resource_refs(data, known) == set()

    def test_dict_keys_scanned(self) -> None:
        known = {"res_a"}
        data = {"{res_a.ext_id}": "value"}
        assert extract_resource_refs(data, known) == {"res_a"}

    def test_fn_tokens_skipped(self) -> None:
        known = {"fn", "pad"}
        data = "{fn.pad(1, 4)}"
        assert extract_resource_refs(data, known) == set()


# ---------------------------------------------------------------------------
# Shared token walker + classify_unresolved_tokens
# ---------------------------------------------------------------------------


class TestIterTokens:
    """Regression coverage for the shared token walker.

    ``_iter_tokens`` replaces three structurally-identical recursive
    walkers; these tests pin down the contract the consumers rely on.
    """

    def test_yields_token_and_parts(self) -> None:
        data = "{res_a.body.name}"
        tokens = list(_iter_tokens(data))
        assert tokens == [("res_a.body.name", ["res_a", "body", "name"])]

    def test_walks_nested_dicts_and_lists(self) -> None:
        data = {"outer": ["{a.x}", {"inner": "{b.y}"}]}
        seen = {token for token, _ in _iter_tokens(data)}
        assert seen == {"a.x", "b.y"}

    def test_dict_keys_are_walked(self) -> None:
        data = {"{res_a.ext_id}": "value"}
        seen = {token for token, _ in _iter_tokens(data)}
        assert seen == {"res_a.ext_id"}

    def test_non_string_leaves_skipped(self) -> None:
        assert list(_iter_tokens(42)) == []
        assert list(_iter_tokens(None)) == []
        assert list(_iter_tokens(True)) == []

    def test_string_without_tokens_short_circuits(self) -> None:
        assert list(_iter_tokens("plain text with no braces")) == []


class TestClassifyUnresolvedTokens:
    """Regression coverage for ``classify_unresolved_tokens``.

    The function partitions tokens into apply-time resource references
    vs. real failures; the three failure branches previously collapsed
    into a single ``else`` so these tests guard that refactor.
    """

    def test_local_resource_ref_is_classified(self) -> None:
        refs, failures = classify_unresolved_tokens(
            "{res_a.ext_id}", known_resources={"res_a"}
        )
        assert refs == {"res_a.ext_id"}
        assert failures == set()

    def test_cross_domain_ref_is_classified(self) -> None:
        refs, failures = classify_unresolved_tokens(
            "{site_a.res_a.ext_id}",
            known_resources={"res_b"},
            known_domains={"site_a"},
        )
        assert refs == {"site_a.res_a.ext_id"}
        assert failures == set()

    def test_scoped_prefix_is_always_failure(self) -> None:
        refs, failures = classify_unresolved_tokens(
            "{var.missing}", known_resources={"var"}
        )
        assert refs == set()
        assert failures == {"var.missing"}

    def test_unknown_resource_is_failure(self) -> None:
        refs, failures = classify_unresolved_tokens(
            "{unknown.ext_id}", known_resources={"res_a"}
        )
        assert refs == set()
        assert failures == {"unknown.ext_id"}

    def test_cross_domain_needs_three_parts(self) -> None:
        # ``{site_a.res_a}`` is only 2 parts; should be classified as
        # failure (not resource ref) even though ``site_a`` is a domain.
        refs, failures = classify_unresolved_tokens(
            "{site_a.res_a}", known_domains={"site_a"}
        )
        assert refs == set()
        assert failures == {"site_a.res_a"}

    def test_walks_nested_structure(self) -> None:
        data = {"a": ["{res_a.ext_id}", {"b": "{var.bad}"}]}
        refs, failures = classify_unresolved_tokens(data, known_resources={"res_a"})
        assert refs == {"res_a.ext_id"}
        assert failures == {"var.bad"}


# ---------------------------------------------------------------------------
# Function resolution
# ---------------------------------------------------------------------------


def _pad(value: object, width: int = 4) -> str:
    return str(int(value)).zfill(int(width))


def _b64encode(value: str) -> str:
    import base64

    return base64.b64encode(value.encode()).decode()


@pytest.fixture
def fn_ctx() -> InterpolationContext:
    """Context with user functions and variables."""
    return InterpolationContext(
        variables={"env": "prod", "index": 7},
        for_each={"key": "vm1", "value": {"idx": 3, "name": "web"}},
        functions={"pad": _pad, "b64encode": _b64encode},
    )


class TestFunctionResolution:
    def test_simple_fn_call(self, fn_ctx: InterpolationContext) -> None:
        assert resolve("{fn.pad(1, 4)}", fn_ctx) == "0001"

    def test_fn_with_var_arg(self, fn_ctx: InterpolationContext) -> None:
        assert resolve("{fn.pad(var.index, 4)}", fn_ctx) == "0007"

    def test_fn_with_each_value_arg(self, fn_ctx: InterpolationContext) -> None:
        assert resolve("{fn.pad(each.value.idx, 2)}", fn_ctx) == "03"

    def test_fn_b64encode(self, fn_ctx: InterpolationContext) -> None:
        assert resolve("{fn.b64encode(hello)}", fn_ctx) == "aGVsbG8="

    def test_nested_fn_calls(self, fn_ctx: InterpolationContext) -> None:
        result = resolve("{fn.b64encode(fn.pad(1, 4))}", fn_ctx)
        import base64

        assert result == base64.b64encode(b"0001").decode()

    def test_fn_in_embedded_string(self, fn_ctx: InterpolationContext) -> None:
        result = resolve("vm-{fn.pad(each.value.idx, 4)}", fn_ctx)
        assert result == "vm-0003"

    def test_unknown_fn_lenient(self, fn_ctx: InterpolationContext) -> None:
        result = resolve("{fn.unknown(1)}", fn_ctx)
        assert result == "{fn.unknown(1)}"

    def test_unknown_fn_strict(self, fn_ctx: InterpolationContext) -> None:
        with pytest.raises(ValueError, match="Unresolved"):
            resolve("{fn.unknown(1)}", fn_ctx, strict=True)

    def test_fn_no_args(self) -> None:
        def greet() -> str:
            return "hello"

        ctx = InterpolationContext(functions={"greet": greet})
        assert resolve("{fn.greet()}", ctx) == "hello"

    def test_fn_without_functions_in_ctx(self) -> None:
        ctx = InterpolationContext()
        result = resolve("{fn.pad(1, 4)}", ctx)
        assert result == "{fn.pad(1, 4)}"

    def test_fn_preserves_type(self) -> None:
        def get_list() -> list[int]:
            return [1, 2, 3]

        ctx = InterpolationContext(functions={"get_list": get_list})
        result = resolve("{fn.get_list()}", ctx)
        assert result == [1, 2, 3]

    def test_fn_exception_returns_unresolved(self) -> None:
        def bad_fn() -> str:
            raise RuntimeError("boom")

        ctx = InterpolationContext(functions={"bad_fn": bad_fn})
        result = resolve("{fn.bad_fn()}", ctx)
        assert result == "{fn.bad_fn()}"

    def test_fn_nested_unresolved_propagates(self) -> None:
        ctx = InterpolationContext(
            functions={"b64encode": _b64encode},
        )
        result = resolve("{fn.b64encode(fn.missing(x))}", ctx)
        assert result == "{fn.b64encode(fn.missing(x))}"

    def test_fn_with_unresolved_arg(self) -> None:
        ctx = InterpolationContext(functions={"pad": _pad})
        result = resolve("{fn.pad(var.missing, 4)}", ctx)
        assert result == "{fn.pad(var.missing, 4)}"

    def test_fn_template_reads_file(self, template_root: Path) -> None:
        tpl = template_root / "test.tpl"
        tpl.write_text("Hello {var.name}!")
        ctx = InterpolationContext(
            variables={"name": "World"},
            functions={},
        )
        from ztf.config.interpolation import _resolve_fn_call

        result = _resolve_fn_call("fn.template(test.tpl)", ctx)
        assert result == "Hello World!"

    def test_fn_template_works_without_user_functions(
        self, template_root: Path
    ) -> None:
        """fn.template is a built-in and must resolve even with no user functions."""
        tpl = template_root / "greeting.tpl"
        tpl.write_text("Hi {var.who}!")
        ctx = InterpolationContext(variables={"who": "ZTF"})
        result = resolve("{fn.template(greeting.tpl)}", ctx)
        assert result == "Hi ZTF!"

    def test_fn_template_missing_file(self, template_root: Path) -> None:
        ctx = InterpolationContext(functions={})
        from ztf.config.interpolation import _resolve_fn_call

        result = _resolve_fn_call("fn.template(nonexistent.tpl)", ctx)
        from ztf.config.interpolation import _UNRESOLVED

        assert result is _UNRESOLVED

    def test_fn_template_rejects_path_traversal(
        self, template_root: Path, tmp_path: Path
    ) -> None:
        """``../`` segments escaping the template root are rejected."""
        outside_dir = tmp_path.parent / "outside-root"
        outside_dir.mkdir(exist_ok=True)
        secret = outside_dir / "secret.tpl"
        secret.write_text("stolen: {var.who}")
        traversal = f"../{outside_dir.name}/secret.tpl"
        ctx = InterpolationContext(variables={"who": "attacker"})
        from ztf.config.interpolation import _UNRESOLVED, _resolve_fn_call

        result = _resolve_fn_call(f"fn.template({traversal})", ctx)
        assert result is _UNRESOLVED

    def test_fn_template_rejects_absolute_path_outside_root(
        self, template_root: Path, tmp_path: Path
    ) -> None:
        """Absolute paths outside the template root are rejected."""
        outside = tmp_path.parent / "evil.tpl"
        outside.write_text("pwned")
        ctx = InterpolationContext()
        from ztf.config.interpolation import _UNRESOLVED, _resolve_fn_call

        result = _resolve_fn_call(f"fn.template({outside})", ctx)
        assert result is _UNRESOLVED

    def test_fn_template_allows_nested_file_under_root(
        self, template_root: Path
    ) -> None:
        """Files nested under the sandbox root are readable."""
        subdir = template_root / "sub"
        subdir.mkdir()
        tpl = subdir / "nested.tpl"
        tpl.write_text("{var.env}")
        ctx = InterpolationContext(variables={"env": "prod"})
        from ztf.config.interpolation import _resolve_fn_call

        result = _resolve_fn_call("fn.template(sub/nested.tpl)", ctx)
        assert result == "prod"

    def test_circular_template_include_bounded(self, template_root: Path) -> None:
        """A template that includes itself must not blow the stack."""
        tpl = template_root / "loop.tpl"
        tpl.write_text("{fn.template(loop.tpl)}")
        ctx = InterpolationContext(functions={})
        # Should terminate gracefully (depth guard kicked in) instead of
        # recursing until Python's stack gives out.
        result = resolve("{fn.template(loop.tpl)}", ctx)
        assert isinstance(result, str)

    def test_chained_template_include_bounded(self, template_root: Path) -> None:
        """Two templates that mutually include each other must terminate."""
        a = template_root / "a.tpl"
        b = template_root / "b.tpl"
        a.write_text("{fn.template(b.tpl)}")
        b.write_text("{fn.template(a.tpl)}")
        ctx = InterpolationContext(functions={})
        result = resolve("{fn.template(a.tpl)}", ctx)
        # Must not raise RecursionError or exceed stack.
        assert isinstance(result, str)

    def test_resolve_token_depth_guard_direct(self) -> None:
        """``_resolve_token`` returns _UNRESOLVED when invoked at the cap."""
        from ztf.config.interpolation import (
            _MAX_TOKEN_DEPTH,
            _UNRESOLVED,
            _resolve_token,
        )

        ctx = InterpolationContext(variables={"x": "y"})
        assert _resolve_token("var.x", ctx, _depth=_MAX_TOKEN_DEPTH) is _UNRESOLVED

    def test_resolve_fn_call_depth_guard_direct(self) -> None:
        """``_resolve_fn_call`` returns _UNRESOLVED when invoked at the cap."""
        from ztf.config.interpolation import (
            _MAX_TOKEN_DEPTH,
            _UNRESOLVED,
            _resolve_fn_call,
        )

        ctx = InterpolationContext(functions={"noop": lambda: "x"})
        assert (
            _resolve_fn_call("fn.noop()", ctx, _depth=_MAX_TOKEN_DEPTH) is _UNRESOLVED
        )

    def test_resolve_fn_call_non_matching_token(self) -> None:
        """Malformed fn tokens return _UNRESOLVED (defensive check)."""
        from ztf.config.interpolation import _UNRESOLVED, _resolve_fn_call

        ctx = InterpolationContext(functions={})
        assert _resolve_fn_call("not.a.fn.call", ctx) is _UNRESOLVED

    def test_fn_template_os_error_surface(
        self, template_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unresolvable OSErrors during path resolution return _UNRESOLVED."""
        import ztf.config.interpolation as interp

        ctx = InterpolationContext(functions={})

        def _boom(self: Path) -> Path:
            raise OSError("simulated disk failure")

        monkeypatch.setattr(Path, "resolve", _boom)
        assert (
            interp._resolve_fn_call("fn.template(test.tpl)", ctx) is interp._UNRESOLVED
        )


# ---------------------------------------------------------------------------
# _split_fn_args paren balance
# ---------------------------------------------------------------------------


class TestSplitFnArgsParenBalance:
    """Mismatched parentheses return the raw string as a single arg."""

    def test_extra_close_paren(self) -> None:
        result = _split_fn_args("a, b)")
        assert result == ["a, b)"]

    def test_unclosed_paren(self) -> None:
        result = _split_fn_args("a, (b, c")
        assert result == ["a, (b, c"]

    def test_balanced_parens_work_normally(self) -> None:
        result = _split_fn_args("fn.inner(x, y), z")
        assert result == ["fn.inner(x, y)", "z"]

    def test_empty_args(self) -> None:
        assert _split_fn_args("") == []
        assert _split_fn_args("   ") == []


# ---------------------------------------------------------------------------
# Dict key resolution safety
# ---------------------------------------------------------------------------


class TestDictKeyResolution:
    """Resolved dict keys are coerced to str when non-string."""

    def test_non_string_key_stringified_lenient(self) -> None:
        ctx = InterpolationContext(variables={"k": 42})
        data = {"{var.k}": "value"}
        result = resolve(data, ctx)
        assert result == {"42": "value"}

    def test_non_string_key_strict_raises(self) -> None:
        ctx = InterpolationContext(variables={"k": [1, 2]})
        data = {"{var.k}": "value"}
        with pytest.raises(ValueError, match="non-string type"):
            resolve(data, ctx, strict=True)

    def test_string_key_passes_through(self) -> None:
        ctx = InterpolationContext(variables={"k": "my_key"})
        data = {"{var.k}": "value"}
        result = resolve(data, ctx)
        assert result == {"my_key": "value"}


# ---------------------------------------------------------------------------
# Nested token resolution
# ---------------------------------------------------------------------------


class TestNestedTokenResolution:
    """Tokens like {data.entity.{fn.pad(each.value, 2)}.data.0.field}
    should resolve inner sub-tokens first, then the outer token."""

    def test_nested_fn_in_data_ref_fully_resolves(self) -> None:
        """When both inner fn and outer data can be resolved, the final
        value is the data source field."""

        def pad(value: object, width: object) -> str:
            return str(value).zfill(int(str(width)))

        ctx = InterpolationContext(
            variables={},
            for_each={"key": "g1", "value": 1},
            functions={"pad": pad},
            data_cache={
                "category": {
                    "dr_gold_01": {
                        "data": [{"extId": "gold-ext-id"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            },
        )
        result = resolve(
            "{data.category.dr_gold_{fn.pad(each.value, 2)}.data.0.extId}", ctx
        )
        assert result == "gold-ext-id"

    def test_nested_fn_partial_resolve_without_data_cache(self) -> None:
        """When inner fn resolves but data cache is unavailable, the
        partially-resolved token is preserved for later resolution."""

        def pad(value: object, width: object) -> str:
            return str(value).zfill(int(str(width)))

        ctx = InterpolationContext(
            variables={},
            for_each={"key": "t1", "value": 1},
            functions={"pad": pad},
        )
        result = resolve(
            "{data.category.app_type_{fn.pad(each.value, 4)}.data.0.extId}", ctx
        )
        assert result == "{data.category.app_type_0001.data.0.extId}"

    def test_nested_var_in_data_ref(self) -> None:
        """Variable tokens inside data references are resolved."""
        ctx = InterpolationContext(
            variables={"tier": "web"},
            data_cache={
                "category": {
                    "app_web": {
                        "data": [{"extId": "web-id"}],
                        "metadata": {"totalAvailableResults": 1},
                    }
                }
            },
        )
        result = resolve("{data.category.app_{var.tier}.data.0.extId}", ctx)
        assert result == "web-id"

    def test_no_nesting_still_works(self) -> None:
        """Non-nested tokens are unaffected by the nesting logic."""
        ctx = InterpolationContext(variables={"env": "prod"})
        assert resolve("{var.env}", ctx) == "prod"
        assert resolve("prefix-{var.env}-suffix", ctx) == "prefix-prod-suffix"


# ---------------------------------------------------------------------------
# Namespaced data cache (_cross / _local)
# ---------------------------------------------------------------------------


class TestNamespacedDataCache:
    """Tests for the ``_cross``/``_local`` namespaced cache shape.

    These resolve through the public ``resolve()`` entrypoint (which
    dispatches to ``_lookup_data_entry_namespaced``) rather than calling
    the private lookup helper directly.
    """

    def test_local_flat_token(self) -> None:
        ctx = InterpolationContext(
            data_cache={
                "_cross": {},
                "_local": {"cluster": {"mine": {"data": [{"extId": "loc-1"}]}}},
            }
        )
        assert resolve("{data.cluster.mine.data.0.extId}", ctx) == "loc-1"

    def test_cross_domain_token(self) -> None:
        ctx = InterpolationContext(
            data_cache={
                "_cross": {
                    "lab1": {"cluster": {"all": {"data": [{"extId": "cross-1"}]}}}
                },
                "_local": {},
            }
        )
        assert resolve("{data.lab1.cluster.all.data.0.extId}", ctx) == "cross-1"

    def test_domain_and_entity_name_collision_resolved_unambiguously(self) -> None:
        """An entity type and a domain sharing the name "cluster" must
        each resolve to their own namespace -- no heuristic ambiguity."""
        ctx = InterpolationContext(
            data_cache={
                "_cross": {
                    "cluster": {
                        "node": {"remote_src": {"data": [{"extId": "remote-1"}]}}
                    }
                },
                "_local": {"cluster": {"local_src": {"data": [{"extId": "local-1"}]}}},
            }
        )
        assert resolve("{data.cluster.node.remote_src.data.0.extId}", ctx) == "remote-1"
        assert resolve("{data.cluster.local_src.data.0.extId}", ctx) == "local-1"

    def test_missing_local_entry_unresolved(self) -> None:
        ctx = InterpolationContext(data_cache={"_cross": {}, "_local": {"cluster": {}}})
        token = "{data.cluster.missing.data.0.extId}"
        assert resolve(token, ctx) == token

    def test_missing_cross_entry_unresolved(self) -> None:
        ctx = InterpolationContext(data_cache={"_cross": {"lab1": {}}, "_local": {}})
        token = "{data.lab1.cluster.missing.data.0.extId}"
        assert resolve(token, ctx) == token


# ---------------------------------------------------------------------------
# validate_data_tokens
# ---------------------------------------------------------------------------


class TestValidateDataTokens:
    """Tests for validate_data_tokens()."""

    def test_known_source_no_warning(self) -> None:
        data_config = {
            "category": {"src1": {"filter": "x"}},
            "node": {"src2": {"parentExtId": "{data.category.src1.data.0.extId}"}},
        }
        warnings = validate_data_tokens(
            data_config, known_sources={"src1", "src2"}, known_domains=set()
        )
        assert warnings == []

    def test_unknown_source_warns(self) -> None:
        data_config = {
            "node": {"src2": {"parentExtId": "{data.category.typo_src.data.0.extId}"}},
        }
        warnings = validate_data_tokens(
            data_config, known_sources={"src2"}, known_domains=set()
        )
        assert len(warnings) == 1
        assert "typo_src" in warnings[0]
        assert "src2" in warnings[0]

    def test_cross_domain_reference_skipped(self) -> None:
        """A valid cross-domain token must not be flagged as an unknown
        within-domain source reference."""
        data_config = {
            "node": {
                "src1": {
                    "parentExtId": "{data.other_domain.category.src_x.data.0.extId}"
                }
            },
        }
        warnings = validate_data_tokens(
            data_config, known_sources={"src1"}, known_domains={"other_domain"}
        )
        assert warnings == []

    def test_incomplete_cross_domain_token_warns(self) -> None:
        data_config = {
            "node": {"src1": {"parentExtId": "{data.other_domain.category}"}},
        }
        warnings = validate_data_tokens(
            data_config, known_sources={"src1"}, known_domains={"other_domain"}
        )
        assert len(warnings) == 1
        assert "incomplete cross-domain token" in warnings[0]

    def test_depends_on_excluded_from_scan(self) -> None:
        """depends_on is an ordering directive, not a token to validate."""
        data_config = {
            "category": {
                "src1": {"filter": "x"},
                "src2": {"filter": "y", "depends_on": ["nonexistent"]},
            },
        }
        warnings = validate_data_tokens(
            data_config, known_sources={"src1", "src2"}, known_domains=set()
        )
        assert warnings == []

    def test_unknown_local_source_when_entity_type_matches_domain(self) -> None:
        """A domain named ``cluster`` must not hide a local typo warning."""
        data_config = {
            "cluster": {
                "src2": {"parentExtId": "{data.cluster.typo_src.data.0.extId}"}
            },
        }
        warnings = validate_data_tokens(
            data_config,
            known_sources={"src2"},
            known_domains={"cluster"},
        )
        assert len(warnings) == 1
        assert "typo_src" in warnings[0]


# ---------------------------------------------------------------------------
# extract_data_source_refs
# ---------------------------------------------------------------------------


class TestExtractDataSourceRefs:
    """Tests for extract_data_source_refs()."""

    def test_local_token(self) -> None:
        data = {"parentExtId": "{data.category.src1.data.0.extId}"}
        refs = extract_data_source_refs(
            data, known_sources={"src1"}, known_entity_types={"category"}
        )
        assert refs == {"src1"}

    def test_cross_domain_token_skipped(self) -> None:
        data = {"parentExtId": "{data.other_domain.category.src_x.data.0.extId}"}
        refs = extract_data_source_refs(
            data, known_sources={"src1"}, known_entity_types={"category"}
        )
        assert refs == set()

    def test_local_ref_when_entity_type_matches_domain_name(self) -> None:
        """A domain named ``cluster`` must not hide a local cluster source."""
        data = {"parentExtId": "{data.cluster.src1.data.0.extId}"}
        refs = extract_data_source_refs(
            data, known_sources={"src1"}, known_entity_types={"cluster"}
        )
        assert refs == {"src1"}


# ---------------------------------------------------------------------------
# extract_indexed_source_tokens
# ---------------------------------------------------------------------------


class TestExtractIndexedSourceTokens:
    """Tests for extract_indexed_source_tokens()."""

    def test_detects_index_access(self) -> None:
        data = {"parentExtId": "{data.category.src1.data.0.extId}"}
        refs = extract_indexed_source_tokens(
            data, known_sources={"src1"}, known_entity_types={"category"}
        )
        assert refs == {("data.category.src1.data.0.extId", "src1")}

    def test_non_index_field_not_flagged(self) -> None:
        data = {"parentExtId": "{data.category.src1.metadata.totalAvailableResults}"}
        refs = extract_indexed_source_tokens(
            data, known_sources={"src1"}, known_entity_types={"category"}
        )
        assert refs == set()

    def test_unknown_source_not_flagged(self) -> None:
        data = {"parentExtId": "{data.category.unknown.data.0.extId}"}
        refs = extract_indexed_source_tokens(
            data, known_sources={"src1"}, known_entity_types={"category"}
        )
        assert refs == set()

    def test_cross_domain_token_skipped(self) -> None:
        data = {"parentExtId": "{data.other_domain.category.src1.data.0.extId}"}
        refs = extract_indexed_source_tokens(
            data, known_sources={"src1"}, known_entity_types={"node"}
        )
        assert refs == set()

    def test_local_ref_when_entity_type_matches_domain_name(self) -> None:
        """A domain named ``cluster`` must not hide local index access."""
        data = {"parentExtId": "{data.cluster.src1.data.0.extId}"}
        refs = extract_indexed_source_tokens(
            data, known_sources={"src1"}, known_entity_types={"cluster"}
        )
        assert refs == {("data.cluster.src1.data.0.extId", "src1")}
