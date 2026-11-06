"""Tests for ztf.config.functions (function loader)."""

import textwrap
from pathlib import Path

import pytest

from ztf.config.functions import (
    discover_functions_file,
    load_functions,
    resolve_functions_file,
)


@pytest.fixture
def valid_functions_file(tmp_path: Path) -> Path:
    """Create a minimal user functions file."""
    fn_file = tmp_path / "functions.py"
    fn_file.write_text(
        textwrap.dedent("""\
        import base64

        MY_CONSTANT = 42

        def pad(value, width=4):
            return str(int(value)).zfill(int(width))

        def b64encode(value):
            return base64.b64encode(value.encode()).decode()

        def _private_helper():
            return "hidden"

        def __dunder():
            return "also hidden"
        """)
    )
    return fn_file


class TestLoadFunctions:
    def test_loads_public_callables(self, valid_functions_file: Path) -> None:
        fns = load_functions(valid_functions_file)
        assert "pad" in fns
        assert "b64encode" in fns
        assert callable(fns["pad"])
        assert callable(fns["b64encode"])

    def test_excludes_private_and_dunder(self, valid_functions_file: Path) -> None:
        fns = load_functions(valid_functions_file)
        assert "_private_helper" not in fns
        assert "__dunder" not in fns

    def test_excludes_imported_modules(self, valid_functions_file: Path) -> None:
        fns = load_functions(valid_functions_file)
        assert "base64" not in fns

    def test_excludes_non_callable_attributes(self, valid_functions_file: Path) -> None:
        fns = load_functions(valid_functions_file)
        assert "MY_CONSTANT" not in fns

    def test_loaded_functions_work(self, valid_functions_file: Path) -> None:
        fns = load_functions(valid_functions_file)
        assert fns["pad"](1, 4) == "0001"
        assert fns["b64encode"]("hello") == "aGVsbG8="

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_functions(tmp_path / "nonexistent.py")

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "functions.py"
        empty.write_text("")
        fns = load_functions(empty)
        assert fns == {}

    def test_excludes_classes(self, tmp_path: Path) -> None:
        fn_file = tmp_path / "functions.py"
        fn_file.write_text(
            textwrap.dedent("""\
            class Helper:
                pass

            def real_fn():
                return 1
            """)
        )
        fns = load_functions(fn_file)
        assert "real_fn" in fns
        assert "Helper" not in fns

    def test_excludes_imported_callables(self, tmp_path: Path) -> None:
        """``from math import sqrt`` must not leak as ``{fn.sqrt}``.

        Only callables defined in the loaded module are exposed; the
        docstring of load_functions() promises this contract, so a
        built-in or imported function must be filtered out even though
        ``inspect.isbuiltin`` / ``inspect.isfunction`` returns True.
        """
        fn_file = tmp_path / "functions.py"
        fn_file.write_text(
            textwrap.dedent("""\
            from math import sqrt
            from os.path import join

            def real_fn():
                return 1
            """)
        )
        fns = load_functions(fn_file)
        assert "real_fn" in fns
        assert "sqrt" not in fns
        assert "join" not in fns

    def test_distinct_paths_get_distinct_module_names(self, tmp_path: Path) -> None:
        """Two different ``functions.py`` files must not share a module name.

        A fixed module name would cause the ``__module__`` attribute of
        user-defined functions in *both* files to collide (breaking
        ``inspect.getmodule``, pickling, and the cross-file ``__module__``
        filter added to exclude imported callables).  The loader now
        hashes the resolved path into a per-file suffix.
        """
        first = tmp_path / "a" / "functions.py"
        second = tmp_path / "b" / "functions.py"
        first.parent.mkdir()
        second.parent.mkdir()
        first.write_text("def one():\n    return 1\n")
        second.write_text("def two():\n    return 2\n")

        fns_a = load_functions(first)
        fns_b = load_functions(second)

        assert fns_a["one"].__module__ != fns_b["two"].__module__
        assert fns_a["one"].__module__.startswith("ztf_user_functions_")
        assert fns_b["two"].__module__.startswith("ztf_user_functions_")

    def test_same_path_is_stable(self, tmp_path: Path) -> None:
        """Loading the same file twice produces the same module name."""
        fn_file = tmp_path / "functions.py"
        fn_file.write_text("def only():\n    return 1\n")
        first = load_functions(fn_file)["only"].__module__
        second = load_functions(fn_file)["only"].__module__
        assert first == second


class TestDiscoverFunctionsFile:
    def test_finds_in_same_dir(self, tmp_path: Path) -> None:
        fn_file = tmp_path / "functions.py"
        fn_file.write_text("def pad(v): return str(v)")
        result = discover_functions_file(str(tmp_path))
        assert result is not None
        assert result.endswith("functions.py")

    def test_finds_in_parent_dir(self, tmp_path: Path) -> None:
        fn_file = tmp_path / "functions.py"
        fn_file.write_text("def pad(v): return str(v)")
        child = tmp_path / "subdir"
        child.mkdir()
        result = discover_functions_file(str(child))
        assert result is not None

    def test_returns_none_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = discover_functions_file(str(tmp_path))
        assert result is None


class TestResolveFunctionsFile:
    def test_explicit_path(self, valid_functions_file: Path) -> None:
        fns = resolve_functions_file(str(valid_functions_file), "input.yml")
        assert "pad" in fns

    def test_auto_discover(self, tmp_path: Path) -> None:
        fn_file = tmp_path / "functions.py"
        fn_file.write_text("def greet(): return 'hi'")
        input_file = tmp_path / "input.yml"
        input_file.write_text("")
        fns = resolve_functions_file(None, str(input_file))
        assert "greet" in fns

    def test_auto_discover_examples_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """functions.py in examples/ is discovered as a fallback."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        fn_file = examples_dir / "functions.py"
        fn_file.write_text("def hello(): return 'world'")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        input_file = config_dir / "input.yml"
        input_file.write_text("")
        monkeypatch.chdir(tmp_path)
        fns = resolve_functions_file(None, str(input_file))
        assert "hello" in fns

    def test_config_dir_takes_priority_over_examples(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """functions.py next to input.yml wins over examples/."""
        examples_dir = tmp_path / "examples"
        examples_dir.mkdir()
        (examples_dir / "functions.py").write_text("def from_examples(): return 1")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "functions.py").write_text("def from_config(): return 2")
        input_file = config_dir / "input.yml"
        input_file.write_text("")
        monkeypatch.chdir(tmp_path)
        fns = resolve_functions_file(None, str(input_file))
        assert "from_config" in fns
        assert "from_examples" not in fns

    def test_no_file_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        input_file = tmp_path / "input.yml"
        input_file.write_text("")
        fns = resolve_functions_file(None, str(input_file))
        assert fns == {}


def test_resolve_functions_file_bad_spec(tmp_path, monkeypatch):
    """An un-importable file should raise ImportError."""
    bad_file = tmp_path / "functions.py"
    bad_file.write_text("x = 1")
    monkeypatch.setattr("importlib.util.spec_from_file_location", lambda *a, **kw: None)
    with pytest.raises(ImportError, match="Cannot create import spec"):
        resolve_functions_file(str(bad_file), "input.yml")
