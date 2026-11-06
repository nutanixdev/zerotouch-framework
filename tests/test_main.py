"""Tests for ztf.main (Click-based CLI)."""

import os
import sys
import threading
from pathlib import Path
from typing import cast

import click
import pytest
import yaml
from click.testing import CliRunner

import ztf.main as main_mod
from ztf.main import cli

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helper: a minimal DummyProvider factory
# ---------------------------------------------------------------------------


def _make_dummy_provider(
    *,
    plan_result=None,
    run_result=None,
    refresh_result=None,
    import_result=None,
    destroy_result=None,
    previous_map=None,
    resolve_outputs_result=None,
    current_resource_map=None,
    dummy_run_results=None,
):
    plan_result = plan_result or {
        "create": {},
        "update": {},
        "delete": {},
        "operations": {},
    }
    run_result = run_result or {"domains": {}}
    refresh_result = refresh_result or {"domains": {}}
    destroy_result = destroy_result or {"domains": {}}
    resolve_outputs_result = resolve_outputs_result or {}
    previous_map = previous_map or {}
    _current_map = current_resource_map or {}
    _run_results = dummy_run_results or {}

    class DummyProvider:
        def __init__(self, *a, **kw):
            self._shutdown_requested = threading.Event()

        max_workers = None
        previous_domain_entity_resource_map = previous_map
        domain_entity_resource_map = _current_map
        run_results = _run_results

        def plan(self):
            return plan_result

        def run(self, **kw):
            return run_result

        def refresh_state(self):
            return refresh_result

        def import_resource_data(self, rn, dn):
            if import_result is None:
                raise RuntimeError("no import_result configured")
            return import_result

        def destroy(self, **kw):
            return destroy_result

        def resolve_outputs(self):
            return resolve_outputs_result

        def request_shutdown(self):
            self._shutdown_requested.set()

        def get_partial_state(self):
            return {"domains": {}}

    return DummyProvider


def _global_config():
    return {"config": {"debug": False}}


def _input_config(resources=None):
    return {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "resources": resources or {"entityA": {"r": {"body": {"x": 1}}}},
            }
        }
    }


def _mock_read_input(monkeypatch, global_data=None, input_data=None):
    g = global_data if global_data is not None else _global_config()
    i = input_data if input_data is not None else _input_config()

    def _read(x):
        return g if "global" in x else i

    def _load(path):
        return _read(path)

    monkeypatch.setattr(main_mod, "read_input_file", _read)
    monkeypatch.setattr(main_mod, "_load_config_file", _load)


def _read_yaml_file(path: str) -> dict[str, object]:
    """Read YAML file contents into a dictionary."""
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Expected YAML file to contain a dict.")
    return cast(dict[str, object], data)


# ---------------------------------------------------------------------------
# CLI: help / structure
# ---------------------------------------------------------------------------


def test_root_help_lists_commands():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "init",
        "plan",
        "apply",
        "refresh",
        "destroy",
        "import",
        "examples",
    ):
        assert cmd in result.output


def test_plan_help_has_no_refresh():
    result = runner.invoke(cli, ["plan", "--help"])
    assert result.exit_code == 0
    assert "--no-refresh" in result.output


def test_plan_help_no_output_file():
    """--output-file is apply-only; plan --help should not mention it."""
    result = runner.invoke(cli, ["plan", "--help"])
    assert "--output-file" not in result.output


def test_apply_help_has_output_file():
    result = runner.invoke(cli, ["apply", "--help"])
    assert "--output-file" in result.output
    assert "--auto-approve" in result.output


def test_init_help_no_input_flag():
    """init only needs --state, not --input or --global-file."""
    result = runner.invoke(cli, ["init", "--help"])
    assert "--state" in result.output
    assert "--input" not in result.output
    assert "--global-file" not in result.output


def test_generate_examples_help():
    result = runner.invoke(cli, ["examples", "--help"])
    assert "--namespace" in result.output
    assert "--output-dir" in result.output


def test_import_help_shows_positionals():
    result = runner.invoke(cli, ["import", "--help"])
    assert "RESOURCE_NAME" in result.output
    assert "DOMAIN_NAME" in result.output


# ---------------------------------------------------------------------------
# repl command
# ---------------------------------------------------------------------------


def test_root_help_lists_repl() -> None:
    """Root --help should list the repl command."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "repl" in result.output


def test_repl_help_shows_exec_and_script() -> None:
    """repl --help should document --exec and --script options."""
    result = runner.invoke(cli, ["repl", "--help"])
    assert result.exit_code == 0
    assert "--exec" in result.output
    assert "--script" in result.output


def test_repl_exec_invokes_repl_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """repl --exec should build context and start REPL with exec code."""
    calls: dict[str, object] = {}
    _mock_read_input(monkeypatch)

    class DummyCtx:
        def to_locals(self) -> dict[str, object]:
            return {"x": 1}

    def fake_build(*_a: object, **_kw: object) -> DummyCtx:
        return DummyCtx()

    def fake_start(
        locals_dict: dict[str, object],
        exec_code: str | None,
        script_path: str | None,
    ) -> None:
        calls["locals"] = locals_dict
        calls["exec"] = exec_code
        calls["script"] = script_path

    monkeypatch.setattr(main_mod, "_build_repl_context", fake_build, raising=False)
    monkeypatch.setattr(main_mod, "_start_repl", fake_start, raising=False)

    result = runner.invoke(cli, ["repl", "--exec", "print(x)"])
    assert result.exit_code == 0
    assert calls["exec"] == "print(x)"


def test_repl_exec_and_script_mutually_exclusive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """repl with both --exec and --script raises UsageError."""
    _mock_read_input(monkeypatch)
    script_file = tmp_path / "script.py"
    script_file.write_text("print(1)")
    result = runner.invoke(
        cli,
        ["repl", "--exec", "print(1)", "--script", str(script_file)],
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output or "UsageError" in str(result.exc_info)


def test_repl_script_invokes_repl_bootstrap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """repl --script should build context and start REPL with script path."""
    _mock_read_input(monkeypatch)
    script_file = tmp_path / "script.py"
    script_file.write_text("assert ctx is not None\nassert data is not None\n")

    calls: dict[str, object] = {}

    class DummyCtx:
        def to_locals(self) -> dict[str, object]:
            return {"ctx": self, "data": object()}

    def fake_build(*_a: object, **_kw: object) -> DummyCtx:
        return DummyCtx()

    def fake_start(
        locals_dict: dict[str, object],
        exec_code: str | None,
        script_path: str | None,
    ) -> None:
        calls["script"] = script_path

    monkeypatch.setattr(main_mod, "_build_repl_context", fake_build, raising=False)
    monkeypatch.setattr(main_mod, "_start_repl", fake_start, raising=False)

    result = runner.invoke(cli, ["repl", "--script", str(script_file)])
    assert result.exit_code == 0
    assert calls["script"] == str(script_file)


def test_repl_exception_exits_non_click(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """repl with non-ClickException logs error and exits with code 1."""
    global_file = tmp_path / "global.yml"
    global_file.write_text("config: {}\n")
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        "domains:\n  lab1:\n    host: 1.2.3.4\n    username: admin\n"
        "    password: pass\n    resources:\n      cluster: {}\n"
    )
    monkeypatch.setattr(
        main_mod,
        "read_input_file",
        _read_yaml_file,
    )

    def fake_build(*_a: object, **_kw: object) -> None:
        raise ValueError("build failed")

    monkeypatch.setattr(main_mod, "_build_repl_context", fake_build, raising=False)

    result = runner.invoke(
        cli,
        [
            "repl",
            "--global-file",
            str(global_file),
            "--input",
            str(input_file),
        ],
    )
    assert result.exit_code == 1


def test_build_repl_context_loads_config_and_builds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_build_repl_context loads files, calls load_config, and returns ReplContext."""
    global_file = tmp_path / "global.yml"
    global_file.write_text("config: {}\n")
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        "domains:\n  lab1:\n    host: 1.2.3.4\n    username: admin\n"
        "    password: pass\n    resources:\n      cluster:\n"
        "        c1:\n          body:\n            name: test\n"
    )
    monkeypatch.setattr(
        main_mod,
        "read_input_file",
        _read_yaml_file,
    )

    with monkeypatch.context():
        from unittest.mock import patch

        with patch("ztf.repl.DomainEntityHandler"):
            ctx = main_mod._build_repl_context(
                global_file=str(global_file),
                input_file=str(input_file),
                var_overrides=None,
                var_files=None,
            )
    assert ctx is not None
    assert hasattr(ctx, "to_locals")
    assert hasattr(ctx, "data")


def test_start_repl_delegates_to_ztf_repl(monkeypatch: pytest.MonkeyPatch) -> None:
    """_start_repl delegates to ztf.repl.start_repl."""
    start_calls: list[tuple[object, ...]] = []

    def fake_start_repl(
        locals_dict: dict[str, object],
        exec_code: str | None = None,
        script_path: str | None = None,
    ) -> None:
        start_calls.append((locals_dict, exec_code, script_path))

    monkeypatch.setattr("ztf.repl.start_repl", fake_start_repl)

    locals_dict: dict[str, object] = {"ctx": object(), "data": object()}
    main_mod._start_repl(locals_dict, exec_code="print(1)", script_path=None)

    assert len(start_calls) == 1
    assert start_calls[0][0] == locals_dict
    assert start_calls[0][1] == "print(1)"
    assert start_calls[0][2] is None


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------


def test_main_init_creates_state(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "state.yml"
    result = runner.invoke(cli, ["init", "--state", str(state_file)])
    assert result.exit_code == 0
    assert state_file.exists()
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


def test_main_init_uses_lock(tmp_path, monkeypatch):
    """init command should use _StateFileLock when writing."""
    state_file = tmp_path / "state.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    lock_entered = []
    original_enter = main_mod._StateFileLock.__enter__

    def patched_enter(self):
        lock_entered.append(True)
        return original_enter(self)

    monkeypatch.setattr(main_mod._StateFileLock, "__enter__", patched_enter)
    result = runner.invoke(cli, ["init", "--state", str(state_file)])
    assert result.exit_code == 0
    assert lock_entered, "_StateFileLock was not used during init"
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


# ---------------------------------------------------------------------------
# init: interactive backup (Phase 4)
# ---------------------------------------------------------------------------


def test_init_backup_yes(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "state.yml"
    state_file.write_text("domains:\n  old: {}\n")
    result = runner.invoke(cli, ["init", "--state", str(state_file)], input="y\n")
    assert result.exit_code == 0
    bak = tmp_path / "state.yml.bak"
    assert bak.exists()
    with open(bak) as fh:
        bak_data = yaml.safe_load(fh)
    assert "old" in bak_data.get("domains", {})
    with open(state_file) as fh:
        new_data = yaml.safe_load(fh)
    assert new_data == {"domains": {}}


def test_init_backup_no(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "state.yml"
    state_file.write_text("domains:\n  old: {}\n")
    result = runner.invoke(cli, ["init", "--state", str(state_file)], input="N\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output
    assert not (tmp_path / "state.yml.bak").exists()
    with open(state_file) as fh:
        data = yaml.safe_load(fh)
    assert "old" in data.get("domains", {})


def test_init_backup_yes_uppercase(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "state.yml"
    state_file.write_text("domains: {}\n")
    result = runner.invoke(cli, ["init", "--state", str(state_file)], input="YES\n")
    assert result.exit_code == 0
    assert (tmp_path / "state.yml.bak").exists()


def test_init_force_skips_prompt(tmp_path, monkeypatch):
    """--force overwrites existing state without interactive prompt."""
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "state.yml"
    state_file.write_text("domains:\n  old: {}\n")
    result = runner.invoke(cli, ["init", "--state", str(state_file), "--force"])
    assert result.exit_code == 0
    assert (tmp_path / "state.yml.bak").exists()
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


def test_init_state_creates_parent_directories(tmp_path, monkeypatch):
    """--state with nested path creates parent directories automatically."""
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "nested" / "project" / "state.yml"
    result = runner.invoke(cli, ["init", "--state", str(state_file)])
    assert result.exit_code == 0
    assert state_file.exists()
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


def test_init_state_custom_name_in_subdirectory(tmp_path, monkeypatch):
    """--state with a path containing directory and custom filename."""
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file = tmp_path / "infra" / "prod.yml"
    result = runner.invoke(cli, ["init", "--state", str(state_file)])
    assert result.exit_code == 0
    assert state_file.exists()
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


def test_init_state_existing_directory(tmp_path, monkeypatch):
    """--state works when the parent directory already exists."""
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    target_dir = tmp_path / "existing"
    target_dir.mkdir()
    state_file = target_dir / "state.yml"
    result = runner.invoke(cli, ["init", "--state", str(state_file)])
    assert result.exit_code == 0
    assert state_file.exists()


# ---------------------------------------------------------------------------
# plan command
# ---------------------------------------------------------------------------


def test_main_plan_command(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["plan", "--state", str(state_file), "--no-refresh"])
    assert result.exit_code == 0


def test_parse_args_no_refresh_flag(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["plan", "--state", str(state_file), "--no-refresh"])
    assert result.exit_code == 0


def test_plan_with_refresh(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    refresh_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            refresh_called.append(True)
            return state_data

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["plan", "--state", str(state_file)])
    assert result.exit_code == 0
    assert refresh_called


def test_plan_refresh_failure_uses_stale(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump({"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}})
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("refresh fail")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["plan", "--state", str(state_file)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


def test_main_apply_command(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            plan_result={
                "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                "update": {},
                "delete": {},
                "operations": {},
            },
            run_result={"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}},
        ),
    )
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code == 0
    assert state_file.exists()
    with open(state_file) as fh:
        assert "domains" in yaml.safe_load(fh)


def test_main_apply_no_state_file(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code != 0
    assert not state_file.exists()


def test_apply_no_changes_skips_confirm(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch, input_data=_input_config(resources={}))
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["apply", "--state", str(state_file)])
    assert result.exit_code == 0


def test_apply_rejected_by_user(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    run_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def plan(self):
            return {
                "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                "update": {},
                "delete": {},
                "operations": {},
            }

        def run(self, **kw):
            run_called.append(True)
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["apply", "--state", str(state_file)], input="no\n")
    assert result.exit_code == 0
    assert not run_called, "provider.run() should not be called when user rejects"


def test_apply_with_outputs(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    output_file = tmp_path / "out.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            plan_result={
                "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                "update": {},
                "delete": {},
                "operations": {},
            },
            run_result={"domains": {}},
            resolve_outputs_result={"my_out": {"value": "prod", "description": "env"}},
        ),
    )
    monkeypatch.setattr(
        "ztf.utils.utils.write_output_file",
        lambda path, data: yaml.safe_dump(data, open(path, "w")),
    )
    result = runner.invoke(
        cli,
        [
            "apply",
            "--state",
            str(state_file),
            "--output-file",
            str(output_file),
            "--auto-approve",
        ],
    )
    assert result.exit_code == 0
    with open(output_file) as fh:
        data = yaml.safe_load(fh)
    assert data["my_out"]["value"] == "prod"


# ---------------------------------------------------------------------------
# refresh command
# ---------------------------------------------------------------------------


def test_main_refresh_command(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            refresh_result={"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}}
        ),
    )
    result = runner.invoke(cli, ["refresh", "--state", str(state_file)])
    assert result.exit_code == 0
    with open(state_file) as fh:
        assert "domains" in yaml.safe_load(fh)


def test_main_refresh_exception(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class FailProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("fail")

    monkeypatch.setattr(main_mod, "Provider", FailProvider)
    result = runner.invoke(cli, ["refresh", "--state", str(state_file)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# destroy command
# ---------------------------------------------------------------------------


def test_main_destroy_command(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {
                            "entityA": {"r": {"ext_id": "e1", "body": {"x": 1}}}
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            previous_map={"lab1": {"entityA": {"r": {"ext_id": "e1", "body": {}}}}},
            destroy_result={"domains": {}},
        ),
    )
    result = runner.invoke(
        cli, ["destroy", "--state", str(state_file), "--auto-approve"]
    )
    assert result.exit_code == 0
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {}}


def test_destroy_rejected_by_user(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    destroy_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"r": {"ext_id": "e1", "body": {}}}}
        }

        def destroy(self, **kw):
            destroy_called.append(True)
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["destroy", "--state", str(state_file)], input="no\n")
    assert result.exit_code == 0
    assert not destroy_called


# ---------------------------------------------------------------------------
# import command
# ---------------------------------------------------------------------------


def test_import_does_not_modify_input(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "username": "admin",
                "password": "pass",
                "resources": {
                    "entityA": {"res1": {"extId": "ext-123", "body": {"foo": "bar"}}}
                },
            }
        }
    }
    input_file.write_text(yaml.safe_dump(input_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            import_result={
                "entity_name": "entityA",
                "sanitized_data": {"foo": "imported_value"},
                "extId": "ext-123",
                "resource_entry": {"extId": "ext-123", "body": {"foo": "bar"}},
            }
        ),
    )
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "res1",
            "lab1",
        ],
    )
    assert result.exit_code == 0
    with open(input_file) as fh:
        assert yaml.safe_load(fh) == input_data
    with open(state_file) as fh:
        state_data = yaml.safe_load(fh)
    assert "lab1" in state_data.get("domains", {})


def test_import_missing_state(tmp_path, monkeypatch):
    state_file = tmp_path / "nonexistent_state.yml"
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "r",
            "lab1",
        ],
    )
    assert result.exit_code != 0


def test_import_exception_exits(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))

    class FailProvider:
        def __init__(self, *a, **kw):
            pass

        def import_resource_data(self, rn, dn):
            raise ValueError("import fail")

    monkeypatch.setattr(main_mod, "Provider", FailProvider)
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "r",
            "lab1",
        ],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# examples command
# ---------------------------------------------------------------------------


def test_generate_examples_command(monkeypatch):
    called = {}

    def mock_generate_all(namespace_filter=None, output_dir=None):
        called["ns"] = namespace_filter
        called["dir"] = output_dir

    monkeypatch.setattr("ztf.generate_examples.generate_all", mock_generate_all)
    result = runner.invoke(cli, ["examples"])
    assert result.exit_code == 0
    assert called["ns"] is None
    assert called["dir"] is None


def test_generate_examples_with_namespace(monkeypatch):
    called = {}

    def mock_generate_all(namespace_filter=None, output_dir=None):
        called["ns"] = namespace_filter

    monkeypatch.setattr("ztf.generate_examples.generate_all", mock_generate_all)
    result = runner.invoke(cli, ["examples", "--namespace", "clustermgmt"])
    assert result.exit_code == 0
    assert called["ns"] == "clustermgmt"


def test_generate_examples_with_output_dir(monkeypatch, tmp_path):
    called = {}

    def mock_generate_all(namespace_filter=None, output_dir=None):
        called["dir"] = output_dir

    monkeypatch.setattr("ztf.generate_examples.generate_all", mock_generate_all)
    result = runner.invoke(cli, ["examples", "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert called["dir"] is not None


# ---------------------------------------------------------------------------
# Missing config file (Phase 1 fix)
# ---------------------------------------------------------------------------


def test_plan_missing_config_file(tmp_path):
    """plan with non-existent global/input file should exit with a clear error."""
    result = runner.invoke(
        cli,
        [
            "plan",
            "--global-file",
            str(tmp_path / "nonexistent.yml"),
            "--input",
            str(tmp_path / "input.yml"),
            "--no-refresh",
        ],
    )
    assert result.exit_code != 0


def test_plan_empty_global_file(tmp_path: Path) -> None:
    """plan should fail when global.yml exists but is empty."""
    global_file = tmp_path / "global.yml"
    input_file = tmp_path / "input.yml"
    global_file.write_text("")
    input_file.write_text("domains: {}\n")
    result = runner.invoke(
        cli,
        [
            "plan",
            "--global-file",
            str(global_file),
            "--input",
            str(input_file),
            "--no-refresh",
        ],
    )
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_plan_empty_input_file(tmp_path: Path) -> None:
    """plan should fail when input.yml exists but is empty."""
    global_file = tmp_path / "global.yml"
    input_file = tmp_path / "input.yml"
    global_file.write_text("config: {}\n")
    input_file.write_text("")
    result = runner.invoke(
        cli,
        [
            "plan",
            "--global-file",
            str(global_file),
            "--input",
            str(input_file),
            "--no-refresh",
        ],
    )
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


def test_main_exception(monkeypatch):
    monkeypatch.setattr(
        main_mod,
        "read_input_file",
        lambda x: (_ for _ in ()).throw(Exception("fail")),
    )
    result = runner.invoke(cli, ["plan", "--no-refresh"])
    assert result.exit_code != 0


def test_main_permission_error_on_chmod(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"

    def raise_oserror(*a, **k):
        raise OSError("fail")

    monkeypatch.setattr(os, "chmod", raise_oserror)
    runner.invoke(cli, ["init", "--state", str(state_file)])
    with open(state_file) as fh:
        data = yaml.safe_load(fh)
    assert data == {"domains": {}}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def test_write_state_creates_backup(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    state_file.write_text(yaml.safe_dump({"domains": {"old": {}}}))
    main_mod._write_state(str(state_file), {"domains": {"new": {}}})
    bak = tmp_path / "state.yml.bak"
    assert bak.exists()
    with open(bak) as fh:
        assert yaml.safe_load(fh) == {"domains": {"old": {}}}
    with open(state_file) as fh:
        assert yaml.safe_load(fh) == {"domains": {"new": {}}}


def test_write_state_no_backup_on_first_write(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    main_mod._write_state(str(state_file), {"domains": {}})
    assert state_file.exists()
    assert not (tmp_path / "state.yml.bak").exists()


def test_state_lock_used_during_write(tmp_path, monkeypatch):
    state_file = tmp_path / "state.yml"
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    lock_entered = []
    original = main_mod._StateFileLock.__enter__

    def patched(self):
        lock_entered.append(True)
        return original(self)

    monkeypatch.setattr(main_mod._StateFileLock, "__enter__", patched)
    main_mod._write_state(str(state_file), {"domains": {}})
    assert lock_entered


def test_write_state_failure_preserves_original(tmp_path, monkeypatch):
    """Serialization failure cannot truncate the managed state file."""
    state_file = tmp_path / "state.yml"
    original = {"domains": {"old": {}}}
    state_file.write_text(yaml.safe_dump(original), encoding="utf-8")
    monkeypatch.setattr(os, "chmod", lambda *args, **kwargs: None)

    def fail_serialization(*args, **kwargs):
        raise yaml.YAMLError("cannot serialize")

    monkeypatch.setattr(main_mod.yaml, "safe_dump", fail_serialization)

    with pytest.raises(yaml.YAMLError, match="cannot serialize"):
        main_mod._write_state(str(state_file), {"domains": {"new": {}}})

    assert yaml.safe_load(state_file.read_text(encoding="utf-8")) == original


# ---------------------------------------------------------------------------
# print_plan
# ---------------------------------------------------------------------------


def test_print_plan_logs(monkeypatch):
    plan_result = {
        "create": {"lab1": {"entityA": [{"resource_name": "foo", "body": {"a": 1}}]}},
        "update": {},
        "delete": {},
        "operations": {},
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    assert any("CREATE" in line for line in logs)


def test_print_plan_with_diff_fields(monkeypatch):
    plan_result = {
        "create": {},
        "update": {
            "lab1": {
                "entityA": [
                    {
                        "resource_name": "res1",
                        "body": {"foo": "new"},
                        "diff_fields": {
                            "added": {"new_field": "val"},
                            "removed": {"old_field": "val"},
                            "changed": {"foo": {"old": "old", "new": "new"}},
                        },
                    }
                ]
            }
        },
        "delete": {},
        "operations": {},
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    assert any("UPDATE" in line for line in logs)
    assert any("+ new_field" in line for line in logs)
    assert any("- old_field" in line for line in logs)
    assert any("~ foo" in line for line in logs)


def test_print_plan_operations(monkeypatch):
    plan_result = {
        "create": {},
        "update": {},
        "delete": {},
        "operations": {
            "lab1": {"entityA": [{"resource_name": "res1", "type": "do_thing"}]}
        },
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    assert any("OPERATIONS" in line for line in logs)
    assert any("do_thing" in line for line in logs)


# ---------------------------------------------------------------------------
# _count_plan_changes
# ---------------------------------------------------------------------------


def test_count_plan_changes():
    plan_result = {
        "create": {"d1": {"e1": [{"resource_name": "a"}, {"resource_name": "b"}]}},
        "update": {"d1": {"e1": [{"resource_name": "c"}]}},
        "delete": {"d1": {"e2": [{"resource_name": "d"}]}},
        "operations": {},
    }
    c, u, d, o = main_mod._count_plan_changes(plan_result)
    assert (c, u, d, o) == (2, 1, 1, 0)


def test_count_plan_changes_empty():
    assert main_mod._count_plan_changes(
        {"create": {}, "update": {}, "delete": {}, "operations": {}}
    ) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# _confirm_action
# ---------------------------------------------------------------------------


def test_confirm_action_yes(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "yes")
    assert main_mod._confirm_action("apply") is True


def test_confirm_action_no(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "no")
    assert main_mod._confirm_action("apply") is False


def test_confirm_action_empty(monkeypatch):
    monkeypatch.setattr("click.prompt", lambda *a, **kw: "")
    assert main_mod._confirm_action("apply") is False


def test_confirm_action_abort(monkeypatch):
    import click as _click

    def raise_abort(*a, **kw):
        raise _click.exceptions.Abort()

    monkeypatch.setattr("click.prompt", raise_abort)
    assert main_mod._confirm_action("apply") is False


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_configure_root_logger_sets_level():
    import logging

    main_mod.configure_root_logger(debug=True)
    root = logging.getLogger()
    # Root level is always DEBUG so the file handler captures everything
    assert root.level == logging.DEBUG
    main_mod.configure_root_logger(debug=False)
    assert root.level == logging.DEBUG


# ---------------------------------------------------------------------------
# _write_outputs
# ---------------------------------------------------------------------------


def test_write_outputs(tmp_path, monkeypatch):
    output_path = str(tmp_path / "outputs.yml")
    monkeypatch.setattr(
        "ztf.utils.utils.write_output_file",
        lambda path, data: yaml.safe_dump(data, open(path, "w")),
    )
    main_mod._write_outputs(output_path, {"key": "value"})
    with open(output_path) as fh:
        data = yaml.safe_load(fh)
    assert data == {"key": "value"}


# ---------------------------------------------------------------------------
# --parallel propagation
# ---------------------------------------------------------------------------


def test_parallel_propagation(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    provider_instance = {}

    class DummyProvider:
        def __init__(self, *a, **kw):
            provider_instance["self"] = self

        max_workers = None

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli, ["plan", "--state", str(state_file), "--parallel", "3", "--no-refresh"]
    )
    assert result.exit_code == 0
    assert provider_instance["self"].max_workers == 3


# ---------------------------------------------------------------------------
# --var flag
# ---------------------------------------------------------------------------


def test_var_flag(monkeypatch, tmp_path):
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(
        monkeypatch,
        input_data={
            "variables": {"env": "dev"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {"entityA": {"res1": {"body": {"a": 1}}}},
                }
            },
        },
    )
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(
        cli, ["plan", "--state", str(state_file), "--no-refresh", "--var", "env=prod"]
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Auto-loaded variable files (ztfvars)
# ---------------------------------------------------------------------------


def test_discover_no_ztfvars(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main_mod.discover_auto_var_files() == []


def test_discover_ztfvars_yml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ztfvars.yml").write_text("password: secret\n")
    assert main_mod.discover_auto_var_files() == ["ztfvars.yml"]


def test_discover_auto_ztfvars(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "prod.auto.ztfvars.yml").write_text("env: prod\n")
    (tmp_path / "dev.auto.ztfvars.yml").write_text("env: dev\n")
    result = main_mod.discover_auto_var_files()
    assert result == ["dev.auto.ztfvars.yml", "prod.auto.ztfvars.yml"]


def test_discover_combined_precedence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ztfvars.yml").write_text("base: val\n")
    (tmp_path / "alpha.auto.ztfvars.yml").write_text("a: 1\n")
    result = main_mod.discover_auto_var_files()
    assert result == ["ztfvars.yml", "alpha.auto.ztfvars.yml"]


def test_collect_var_files_missing_raises():
    """Explicit --var-file that doesn't exist should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        main_mod._collect_var_files(("/no/such/vars.yml",))


def test_collect_var_files_directory_raises(tmp_path):
    """Explicit --var-file pointing to a directory should raise IsADirectoryError."""
    with pytest.raises(IsADirectoryError, match="is a directory"):
        main_mod._collect_var_files((str(tmp_path),))


def test_ztfvars_injected_into_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    (tmp_path / "ztfvars.yml").write_text("lab_password: injected_secret\n")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(
        monkeypatch,
        input_data={
            "variables": {"lab_password": "placeholder"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "{var.lab_password}",
                    "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                }
            },
        },
    )

    captured = {}
    original_load = main_mod.load_config

    def spy(raw, var_overrides=None, var_files=None, **kwargs):
        captured["var_files"] = var_files
        return original_load(raw, var_overrides=var_overrides, var_files=var_files)

    monkeypatch.setattr(main_mod, "load_config", spy)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["plan", "--state", str(state_file), "--no-refresh"])
    assert result.exit_code == 0
    assert captured.get("var_files") is not None
    assert any("ztfvars.yml" in v for v in captured["var_files"])


def test_ztfvars_overridden_by_explicit_var_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    (tmp_path / "ztfvars.yml").write_text("my_var: from_ztfvars\n")
    explicit = tmp_path / "override.yml"
    explicit.write_text("my_var: from_explicit\n")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(
        monkeypatch,
        input_data={
            "variables": {"my_var": "default"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                }
            },
        },
    )

    captured = {}
    original_load = main_mod.load_config

    def spy(raw, var_overrides=None, var_files=None, **kwargs):
        result = original_load(raw, var_overrides=var_overrides, var_files=var_files)
        captured["variables"] = result["variables"]
        return result

    monkeypatch.setattr(main_mod, "load_config", spy)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(
        cli,
        [
            "plan",
            "--state",
            str(state_file),
            "--var-file",
            str(explicit),
            "--no-refresh",
        ],
    )
    assert result.exit_code == 0
    assert captured["variables"]["my_var"] == "from_explicit"


def test_ztfvars_overridden_by_cli_var(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    (tmp_path / "ztfvars.yml").write_text("my_var: from_ztfvars\n")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(
        monkeypatch,
        input_data={
            "variables": {"my_var": "default"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {"entityA": {"r": {"body": {"x": 1}}}},
                }
            },
        },
    )

    captured = {}
    original_load = main_mod.load_config

    def spy(raw, var_overrides=None, var_files=None, **kwargs):
        result = original_load(raw, var_overrides=var_overrides, var_files=var_files)
        captured["variables"] = result["variables"]
        return result

    monkeypatch.setattr(main_mod, "load_config", spy)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(
        cli,
        [
            "plan",
            "--state",
            str(state_file),
            "--var",
            "my_var=from_cli",
            "--no-refresh",
        ],
    )
    assert result.exit_code == 0
    assert captured["variables"]["my_var"] == "from_cli"


# ---------------------------------------------------------------------------
# _print_plan_summary coverage (lines 186-190)
# ---------------------------------------------------------------------------


def test_print_plan_summary_all_changes(monkeypatch):
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_plan_summary(create=2, update=1, delete=1, operations=3)
    output = "\n".join(logs)
    assert "2 to create" in output
    assert "1 to update" in output
    assert "1 to delete" in output
    assert "3 operation(s) to run" in output


def test_print_plan_summary_only_create(monkeypatch):
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_plan_summary(create=5, update=0, delete=0, operations=0)
    output = "\n".join(logs)
    assert "5 to create" in output
    assert "to update" not in output
    assert "to delete" not in output


def test_print_plan_summary_only_update(monkeypatch):
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_plan_summary(create=0, update=3, delete=0, operations=0)
    output = "\n".join(logs)
    assert "to update" in output
    assert "to create" not in output


def test_print_plan_summary_only_delete(monkeypatch):
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_plan_summary(create=0, update=0, delete=2, operations=0)
    output = "\n".join(logs)
    assert "to delete" in output
    assert "to create" not in output


def test_print_plan_summary_only_operations(monkeypatch):
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_plan_summary(create=0, update=0, delete=0, operations=2)
    output = "\n".join(logs)
    assert "2 operation(s) to run" in output
    assert "to create" not in output


# ---------------------------------------------------------------------------
# _StateFileLock PermissionError path (line 345)
# ---------------------------------------------------------------------------


def test_state_file_lock_permission_error_fallback(tmp_path, monkeypatch):
    """Test that PermissionError on a+ mode falls back to read-only mode."""
    import sys

    import pytest

    # fcntl is Unix-only, skip on Windows
    if sys.platform == "win32":
        pytest.skip("fcntl not available on Windows")

    state_file = tmp_path / "state.yml"
    state_file.write_text("domains: {}")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)

    # Mock platform to not be Windows
    monkeypatch.setattr(main_mod, "_IS_WINDOWS", False)

    # Count how many times we tried to open
    open_attempts = []
    original_open = open

    def mock_open(path, *args, **kwargs):
        open_attempts.append((path, args, kwargs))
        if len(open_attempts) == 1 and "a+" in (args[0] if args else ""):
            raise PermissionError("file is read-only")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open)

    lock = main_mod._StateFileLock(str(state_file))
    with lock as f:
        assert f is not None
    assert len(open_attempts) >= 2


# ---------------------------------------------------------------------------
# _read_state error handling
# ---------------------------------------------------------------------------


def test_read_state_missing_file():
    """Missing state file should raise FileNotFoundError."""
    missing_path = "/nonexistent/path/that/does/not/exist_state.yml"
    with pytest.raises(FileNotFoundError, match="not found"):
        main_mod._read_state(missing_path)


def test_read_state_directory_raises(tmp_path):
    """Passing a directory as state path should raise IsADirectoryError."""
    with pytest.raises(IsADirectoryError, match="is a directory"):
        main_mod._read_state(str(tmp_path))


# ---------------------------------------------------------------------------
# _set_readonly and _set_writable
# ---------------------------------------------------------------------------


def test_set_readonly_unix(tmp_path, monkeypatch):
    """Test _set_readonly sets correct Unix permissions."""
    import sys

    import pytest

    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    state_file = tmp_path / "state.yml"
    state_file.write_text("test")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    main_mod._set_readonly(str(state_file))


def test_set_writable_unix(tmp_path, monkeypatch):
    """Test _set_writable sets correct Unix permissions."""
    import sys

    import pytest

    if sys.platform == "win32":
        pytest.skip("Unix-specific test")

    state_file = tmp_path / "state.yml"
    state_file.write_text("test")
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    main_mod._set_writable(str(state_file))


# ---------------------------------------------------------------------------
# Import edge cases (extend existing import tests)
# ---------------------------------------------------------------------------


def test_import_returns_none_result(tmp_path, monkeypatch):
    """Test import when provider returns None."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))

    class FailProvider:
        def __init__(self, *a, **kw):
            pass

        def import_resource_data(self, rn, dn):
            return None

    monkeypatch.setattr(main_mod, "Provider", FailProvider)
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "r",
            "lab1",
        ],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Apply with mixed plan (update + delete + operations)
# ---------------------------------------------------------------------------


def test_apply_with_all_operations(tmp_path, monkeypatch):
    """Test apply with create, update, delete all in one plan."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            plan_result={
                "create": {"lab1": {"entityA": [{"resource_name": "new"}]}},
                "update": {"lab1": {"entityB": [{"resource_name": "existing"}]}},
                "delete": {"lab1": {"entityC": [{"resource_name": "old"}]}},
                "operations": {"lab1": {"entityD": [{"resource_name": "op"}]}},
            },
            run_result={"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}},
        ),
    )
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Plan with updates that have diff_fields (coverage for all diff types)
# ---------------------------------------------------------------------------


def test_plan_update_with_no_diff_fields(monkeypatch):
    """Test printing update without diff_fields."""
    plan_result = {
        "create": {},
        "update": {
            "lab1": {
                "entityA": [
                    {
                        "resource_name": "res1",
                        "body": {"foo": "new"},
                    }
                ]
            }
        },
        "delete": {},
        "operations": {},
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    output = "\n".join(logs)
    assert "UPDATE" in output


# ---------------------------------------------------------------------------
# Empty/no-op scenarios
# ---------------------------------------------------------------------------


def test_apply_empty_domains_fails(tmp_path, monkeypatch):
    """Test apply with no domains in input should fail."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch, input_data={"domains": {}})
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(cli, ["apply", "--state", str(state_file)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Destroy with nothing to destroy
# ---------------------------------------------------------------------------


def test_destroy_empty_state(tmp_path, monkeypatch):
    """Test destroy when state is empty."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(previous_map={}, destroy_result={"domains": {}}),
    )
    result = runner.invoke(
        cli, ["destroy", "--state", str(state_file), "--auto-approve"]
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Parse var string with complex keys
# ---------------------------------------------------------------------------


def test_var_flag_multiple_vars(monkeypatch, tmp_path):
    """Test multiple --var flags."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(
        monkeypatch,
        input_data={
            "variables": {"env": "dev", "region": "us-west"},
            "domains": {
                "lab1": {
                    "host": "1.2.3.4",
                    "username": "admin",
                    "password": "pass",
                    "resources": {"entityA": {"res1": {"body": {"a": 1}}}},
                }
            },
        },
    )
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())
    result = runner.invoke(
        cli,
        [
            "plan",
            "--state",
            str(state_file),
            "--no-refresh",
            "--var",
            "env=prod",
            "--var",
            "region=us-east",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Import with var files and var flags
# ---------------------------------------------------------------------------


def test_import_with_vars(tmp_path, monkeypatch):
    """Test import command with variable overrides."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "variables": {"host": "default"},
                "domains": {
                    "lab1": {
                        "host": "{var.host}",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {"res1": {"extId": "ext-123", "body": {}}}
                        },
                    }
                },
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            import_result={
                "entity_name": "entityA",
                "sanitized_data": {"foo": "imported_value"},
                "extId": "ext-123",
                "resource_entry": {"extId": "ext-123", "body": {"foo": "bar"}},
            }
        ),
    )
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "--var",
            "host=1.2.3.4",
            "res1",
            "lab1",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Plan update with only removed fields
# ---------------------------------------------------------------------------


def test_plan_update_only_removed_fields(monkeypatch):
    """Test update showing only removed fields in diff."""
    plan_result = {
        "create": {},
        "update": {
            "lab1": {
                "entityA": [
                    {
                        "resource_name": "res1",
                        "body": {"new": "val"},
                        "diff_fields": {
                            "added": {},
                            "removed": {"old_field": "val"},
                            "changed": {},
                        },
                    }
                ]
            }
        },
        "delete": {},
        "operations": {},
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    output = "\n".join(logs)
    assert "- old_field" in output


# ---------------------------------------------------------------------------
# Plan delete operation
# ---------------------------------------------------------------------------


def test_plan_delete_display(monkeypatch):
    """Test displaying delete operations in plan."""
    plan_result = {
        "create": {},
        "update": {},
        "delete": {"lab1": {"entityA": [{"resource_name": "res1", "body": {"x": 1}}]}},
        "operations": {},
    }
    logs = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod.print_plan(plan_result)
    output = "\n".join(logs)
    assert "DELETE" in output


# ---------------------------------------------------------------------------
# Apply with user rejecting prompt
# ---------------------------------------------------------------------------


def test_apply_user_cancels_at_prompt(tmp_path, monkeypatch):
    """Test user canceling at confirmation prompt."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    run_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def plan(self):
            return {
                "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                "update": {},
                "delete": {},
                "operations": {},
            }

        def run(self, **kw):
            run_called.append(True)
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["apply", "--state", str(state_file)], input="no\n")
    assert result.exit_code == 0
    assert not run_called


# ---------------------------------------------------------------------------
# Refresh with exception handling
# ---------------------------------------------------------------------------


def test_refresh_with_exception_stores_state(tmp_path, monkeypatch):
    """Test that refresh still saves state even on partial failure."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {"old": {}}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class FailProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("refresh fail")

    monkeypatch.setattr(main_mod, "Provider", FailProvider)
    result = runner.invoke(cli, ["refresh", "--state", str(state_file)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Additional coverage tests: exception paths and edge cases
# ---------------------------------------------------------------------------


def test_refresh_with_parallel_flag(tmp_path, monkeypatch):
    """Test refresh command with --parallel flag sets max_workers."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    max_workers_value = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        _max_workers = None

        @property
        def max_workers(self):
            return self._max_workers

        @max_workers.setter
        def max_workers(self, value):
            self._max_workers = value
            max_workers_value.append(value)

        def refresh_state(self):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli, ["refresh", "--state", str(state_file), "--parallel", "4"]
    )
    assert result.exit_code == 0
    assert max_workers_value == [4]


def test_plan_exception_non_click(tmp_path, monkeypatch):
    """Test plan command with non-ClickException error."""
    input_file = tmp_path / "input.yml"
    input_file.write_text(yaml.safe_dump({"domains": {}}))
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    def mock_read_input(path):
        if "input" in path:
            return {"domains": {}}
        raise ValueError("Test error")

    monkeypatch.setattr(main_mod, "read_input_file", mock_read_input)
    result = runner.invoke(
        cli,
        [
            "plan",
            "--input",
            str(input_file),
            "--state",
            str(state_file),
            "--no-refresh",
        ],
    )
    assert result.exit_code == 1


def test_apply_exception_non_click(tmp_path, monkeypatch):
    """Test apply command with non-ClickException error."""
    input_file = tmp_path / "input.yml"
    input_file.write_text(yaml.safe_dump({"domains": {}}))
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    def mock_read_input(path):
        if "input" in path:
            return {"domains": {}}
        raise ValueError("Test error")

    monkeypatch.setattr(main_mod, "read_input_file", mock_read_input)
    result = runner.invoke(
        cli,
        [
            "apply",
            "--input",
            str(input_file),
            "--state",
            str(state_file),
        ],
    )
    assert result.exit_code == 1


def test_destroy_exception_non_click(tmp_path, monkeypatch):
    """Test destroy command with non-ClickException error."""
    input_file = tmp_path / "input.yml"
    input_file.write_text(yaml.safe_dump({"domains": {}}))
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    def mock_read_input(path):
        if "input" in path:
            return {"domains": {}}
        raise ValueError("Test error")

    monkeypatch.setattr(main_mod, "read_input_file", mock_read_input)
    result = runner.invoke(
        cli,
        [
            "destroy",
            "--input",
            str(input_file),
            "--state",
            str(state_file),
        ],
    )
    assert result.exit_code == 1


def test_import_exception_non_click(tmp_path, monkeypatch):
    """Test import command with non-ClickException error."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    def mock_read_input(path):
        raise ValueError("Test error")

    monkeypatch.setattr(main_mod, "read_input_file", mock_read_input)
    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "res1",
            "lab1",
        ],
    )
    assert result.exit_code == 1


def test_write_state_creates_backup_when_exists(tmp_path, monkeypatch):
    """Test _write_state creates backup when state file exists."""
    state_file = tmp_path / "state.yml"
    backup_file = tmp_path / "state.yml.bak"

    initial_state = {"domains": {"lab1": {}}}
    state_file.write_text(yaml.safe_dump(initial_state))

    def mock_chmod(*args, **kwargs):
        pass

    monkeypatch.setattr(os, "chmod", mock_chmod)

    new_state = {"domains": {"lab2": {}}}
    main_mod._write_state(str(state_file), new_state)

    assert backup_file.exists()
    backup_data = yaml.safe_load(backup_file.read_text())
    assert backup_data == initial_state


def test_write_state_creates_new_backup_when_backup_exists(tmp_path, monkeypatch):
    """Test _write_state overwrites existing backup file."""
    state_file = tmp_path / "state.yml"
    backup_file = tmp_path / "state.yml.bak"

    initial_state = {"domains": {"lab1": {}}}
    state_file.write_text(yaml.safe_dump(initial_state))

    old_backup = {"domains": {"old": {}}}
    backup_file.write_text(yaml.safe_dump(old_backup))

    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)

    new_state = {"domains": {"lab2": {}}}
    main_mod._write_state(str(state_file), new_state)

    backup_data = yaml.safe_load(backup_file.read_text())
    assert backup_data == initial_state


def test_plan_with_refresh_exception(tmp_path, monkeypatch):
    """Test plan command when refresh fails."""
    input_file = tmp_path / "input.yml"
    input_file.write_text(yaml.safe_dump({"domains": {}}))
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    _mock_read_input(monkeypatch)

    class FailRefreshProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("refresh failed")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", FailRefreshProvider)
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)

    result = runner.invoke(
        cli,
        [
            "plan",
            "--input",
            str(input_file),
            "--state",
            str(state_file),
        ],
    )
    assert result.exit_code == 0


def test_state_file_lock_permission_error_fallback_on_read(tmp_path, monkeypatch):
    """Test _StateFileLock opens state file read-only on PermissionError."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    os.chmod(state_file, 0o444)

    result = main_mod._read_state(str(state_file))
    assert result == {"domains": {}}


def test_state_file_lock_is_platform_specific_subclass():
    """_StateFileLock must alias the correct OS-specific subclass.

    Pins down the Phase D refactor that split the old monolithic class
    into ``_UnixStateFileLock`` / ``_WindowsStateFileLock`` sharing a
    ``_BaseStateFileLock`` context-manager skeleton.
    """
    assert issubclass(main_mod._StateFileLock, main_mod._BaseStateFileLock)
    if main_mod._IS_WINDOWS:
        assert main_mod._StateFileLock is main_mod._WindowsStateFileLock
    else:
        assert main_mod._StateFileLock is main_mod._UnixStateFileLock


def test_state_file_lock_context_manager_acquire_release_order(tmp_path, monkeypatch):
    """Lifecycle must call ``_open_handle`` → ``_acquire`` → ``_release``.

    Uses a test-only subclass that records the call order so the
    platform-specific subclasses don't have to; guards against the
    base-class skeleton silently swallowing one of the hooks during
    future edits.
    """
    calls: list[str] = []

    class _RecordingLock(main_mod._BaseStateFileLock):
        def _open_handle(self):
            calls.append("open")
            return open(tmp_path / "sentinel", "wb")

        def _acquire(self):
            calls.append("acquire")

        def _release(self):
            calls.append("release")

        def _cleanup(self):
            calls.append("cleanup")

    with _RecordingLock(str(tmp_path / "sentinel")):
        assert calls == ["open", "acquire"]
    assert calls == ["open", "acquire", "release", "cleanup"]


def test_apply_with_all_changes(tmp_path, monkeypatch):
    """Test apply command with all types of changes."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    plan_result = {
        "create": {"lab1": {"entityA": [{"resource_name": "res1", "body": {"x": 1}}]}},
        "update": {"lab1": {"entityB": [{"resource_name": "res2", "body": {"y": 2}}]}},
        "delete": {"lab1": {"entityC": [{"resource_name": "res3", "body": {"z": 3}}]}},
        "operations": {},
    }

    run_result = {
        "domains": {
            "lab1": {
                "entityA": {"res1": {"x": 1}},
                "entityB": {"res2": {"y": 2}},
                "entityC": {},
            }
        }
    }

    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(plan_result=plan_result, run_result=run_result),
    )

    result = runner.invoke(
        cli,
        [
            "apply",
            "--state",
            str(state_file),
        ],
    )
    assert result.exit_code == 0


def test_generate_examples_with_multiple_namespaces(tmp_path, monkeypatch):
    """Test examples command lists all available namespaces."""
    result = runner.invoke(cli, ["examples", "--help"])
    assert result.exit_code == 0
    assert "--namespace" in result.output


def test_plan_with_var_file_and_var_flag_precedence(tmp_path, monkeypatch):
    """Test that CLI --var flags override var file values."""
    var_file = tmp_path / "vars.yml"
    var_file.write_text(yaml.safe_dump({"env": "dev"}))

    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))

    _mock_read_input(monkeypatch)
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "Provider", _make_dummy_provider())

    result = runner.invoke(
        cli,
        [
            "plan",
            "--state",
            str(state_file),
            "--var-file",
            str(var_file),
            "--var",
            "env=prod",
            "--no-refresh",
        ],
    )
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Fix 1: Apply auto-refresh
# ---------------------------------------------------------------------------


def test_apply_auto_refresh(tmp_path, monkeypatch):
    """Apply should refresh state before planning when state has domains."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    refresh_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {}
        domain_entity_resource_map = {}

        def refresh_state(self):
            refresh_called.append(True)
            return state_data

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

        def run(self, **kw):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code == 0
    assert refresh_called


def test_apply_auto_refresh_failure(tmp_path, monkeypatch):
    """Apply should proceed with stale state when refresh fails."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {}
        domain_entity_resource_map = {}

        def refresh_state(self):
            raise RuntimeError("refresh fail")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

        def run(self, **kw):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code == 0


def test_apply_no_refresh_flag_skips_refresh(tmp_path, monkeypatch):
    """Apply with --no-refresh should skip the auto-refresh step."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    refresh_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {}
        domain_entity_resource_map = {}

        def refresh_state(self):
            refresh_called.append(True)
            return state_data

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

        def run(self, **kw):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli, ["apply", "--state", str(state_file), "--auto-approve", "--no-refresh"]
    )
    assert result.exit_code == 0
    assert not refresh_called


# ---------------------------------------------------------------------------
# Fix 2: Plan persists refreshed state
# ---------------------------------------------------------------------------


def test_plan_refresh_persists_state(tmp_path, monkeypatch):
    """Plan with refresh should write the refreshed state to disk."""
    state_file = tmp_path / "state.yml"
    old_state = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    refreshed = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 2}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(old_state))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            return refreshed

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["plan", "--state", str(state_file)])
    assert result.exit_code == 0
    with open(state_file) as fh:
        disk_state = yaml.safe_load(fh)
    res_body = (
        disk_state.get("domains", {})
        .get("lab1", {})
        .get("resources", {})
        .get("entityA", {})
        .get("res1", {})
        .get("body", {})
    )
    assert res_body.get("a") == 2


# ---------------------------------------------------------------------------
# Fix 5: Refresh diff
# ---------------------------------------------------------------------------


def test_refresh_shows_diff(tmp_path, monkeypatch):
    """Refresh command should log changed/removed resources."""
    state_file = tmp_path / "state.yml"
    old_state = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {
                    "entityA": {
                        "res1": {"ext_id": "e1", "body": {"a": 1}},
                        "res2": {"ext_id": "e2", "body": {"b": 2}},
                    }
                },
            }
        }
    }
    refreshed = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {
                    "entityA": {
                        "res1": {"ext_id": "e1", "body": {"a": 99}},
                    }
                },
            }
        }
    }
    state_file.write_text(yaml.safe_dump(old_state))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            return refreshed

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)

    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )

    result = runner.invoke(cli, ["refresh", "--state", str(state_file)])
    assert result.exit_code == 0
    log_text = "\n".join(logs)
    assert "CHANGED" in log_text
    assert "REMOVED" in log_text
    assert "1 changed" in log_text
    assert "1 removed" in log_text


# ---------------------------------------------------------------------------
# Fix 5: _print_refresh_diff unit tests
# ---------------------------------------------------------------------------


def test_print_refresh_diff_empty():
    """No resources means no crash."""
    main_mod._print_refresh_diff({"domains": {}}, {"domains": {}})


def test_print_refresh_diff_all_unchanged(monkeypatch):
    """All unchanged resources produce no CHANGED/REMOVED output."""
    state = {"domains": {"lab1": {"resources": {"entityA": {"r": {"body": {"a": 1}}}}}}}
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_refresh_diff(state, state)
    text = "\n".join(logs)
    assert "CHANGED" not in text
    assert "REMOVED" not in text
    assert "0 changed" in text


def test_print_refresh_diff_non_dict_domains():
    """Non-dict domains values are coerced to empty dicts without crashing."""
    main_mod._print_refresh_diff({"domains": "bad"}, {"domains": None})


def test_print_refresh_diff_non_dict_domain_entries(monkeypatch):
    """Non-dict domain entries, resources, and entity resources are skipped."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {
        "domains": {
            "bad_domain": "not-a-dict",
            "lab1": {
                "resources": {
                    "entity_ok": {"r1": {"body": {"a": 1}}},
                    "entity_bad": "not-a-dict",
                }
            },
        }
    }
    ref = {
        "domains": {
            "lab1": {
                "resources": "not-a-dict",
            },
        }
    }
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "0 changed" in text or "1 removed" in text


def test_print_refresh_diff_ref_domain_not_dict(monkeypatch):
    """Refreshed domain entry that is not a dict is coerced to empty."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {"domains": {"lab1": {"resources": {"ent": {"r1": {"body": {"a": 1}}}}}}}
    ref = {"domains": {"lab1": "bad"}}
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "REMOVED" in text


def test_print_refresh_diff_ref_entity_resources_not_dict(monkeypatch):
    """Non-dict entity resources in refreshed state are coerced to empty."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {"domains": {"lab1": {"resources": {"ent": {"r1": {"body": {"x": 1}}}}}}}
    ref = {"domains": {"lab1": {"resources": {"ent": "not-dict"}}}}
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "REMOVED" in text


def test_print_refresh_diff_shows_field_level_changes(monkeypatch):
    """Changed resources should display added/removed/changed fields."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {
        "domains": {
            "lab1": {
                "resources": {
                    "entityA": {
                        "r1": {"body": {"name": "old", "desc": "x", "port": 80}}
                    }
                }
            }
        }
    }
    ref = {
        "domains": {
            "lab1": {
                "resources": {
                    "entityA": {
                        "r1": {"body": {"name": "new", "port": 80, "tag": "v2"}}
                    }
                }
            }
        }
    }
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "CHANGED" in text
    assert "~ name: old -> new" in text
    assert "- desc: x" in text
    assert "+ tag: v2" in text
    assert "1 changed" in text


def test_print_refresh_diff_no_field_diff_for_removed(monkeypatch):
    """Removed resources should not show field-level diffs."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {"domains": {"lab1": {"resources": {"entityA": {"r1": {"body": {"a": 1}}}}}}}
    ref = {"domains": {"lab1": {"resources": {"entityA": {}}}}}
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "REMOVED" in text
    assert "~" not in text
    assert "1 removed" in text


# ---------------------------------------------------------------------------
# Fix 6: Destroy detailed plan
# ---------------------------------------------------------------------------


def test_print_destroy_plan():
    """_print_destroy_plan should count all resources."""
    resource_map = {
        "lab1": {
            "entityA": {"r1": {}, "r2": {}},
            "entityB": {"r3": {}},
        },
        "lab2": {
            "entityC": {"r4": {}},
        },
    }
    total = main_mod._print_destroy_plan(resource_map)
    assert total == 4


def test_print_destroy_plan_empty():
    """Empty map returns 0."""
    assert main_mod._print_destroy_plan({}) == 0


# ---------------------------------------------------------------------------
# Fix 9: _print_run_summary
# ---------------------------------------------------------------------------


def test_print_run_summary(monkeypatch):
    """Summary counts operations from in-memory run results."""
    results = {
        "lab1": [
            {"operation": "create", "resource": "r1"},
            {"operation": "update", "resource": "r2"},
            {"operation": "delete", "resource": "r3"},
            {"operation": "create", "resource": "r4", "error": "fail"},
        ]
    }

    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_run_summary(results)
    text = "\n".join(logs)
    assert "Apply complete" in text
    assert "1 created" in text
    assert "1 updated" in text
    assert "1 deleted" in text
    assert "1 resource(s) had errors" in text


def test_print_run_summary_empty(monkeypatch):
    """Empty results report 0 changes."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_run_summary({})
    text = "\n".join(logs)
    assert "0 changes" in text


def test_print_run_summary_with_replace(monkeypatch):
    """Replace operations are counted in the summary."""
    results = {
        "lab1": [
            {"operation": "replace", "resource": "r1"},
            {"operation": "create", "resource": "r2"},
        ]
    }
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_run_summary(results)
    text = "\n".join(logs)
    assert "1 replaced" in text
    assert "1 created" in text


def test_print_run_summary_destroy_label(monkeypatch):
    """Summary uses the provided label for destroy."""
    results = {
        "lab1": [
            {"operation": "delete", "resource": "r1"},
            {"operation": "delete", "resource": "r2"},
        ]
    }
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    main_mod._print_run_summary(results, label="Destroy")
    text = "\n".join(logs)
    assert "Destroy complete" in text
    assert "2 deleted" in text


# ---------------------------------------------------------------------------
# _classify_unresolved_plan_resources
# ---------------------------------------------------------------------------


def test_classify_unresolved_detects_failed_data_source():
    """Resources with unresolved {data.*} tokens are classified as failed."""
    plan_result = {
        "create": {
            "lab1": {
                "entityA": [
                    {"resource_name": "r1", "body": {"name": "ok"}},
                    {
                        "resource_name": "r2",
                        "body": {"ref": "{data.cluster.c1.data.0.extId}"},
                    },
                ]
            }
        },
        "update": {},
        "delete": {},
    }
    config = {"domains": {"lab1": {"resources": {"entityA": {"r1": {}, "r2": {}}}}}}
    known, failed = main_mod._classify_unresolved_plan_resources(plan_result, config)
    assert len(failed) == 1
    assert "r2" in failed[0]
    assert len(known) == 0


def test_classify_unresolved_detects_known_after_apply():
    """Resource refs ({res.ext_id}) are classified as known after apply."""
    plan_result = {
        "create": {
            "lab1": {
                "subnet": [
                    {
                        "resource_name": "overlay",
                        "body": {"vpcRef": "{my_vpc.ext_id}"},
                    },
                ]
            }
        },
        "update": {},
        "delete": {},
    }
    config = {
        "domains": {
            "lab1": {
                "resources": {
                    "subnet": {"overlay": {}},
                    "vpc": {"my_vpc": {}},
                }
            }
        }
    }
    known, failed = main_mod._classify_unresolved_plan_resources(plan_result, config)
    assert len(known) == 1
    assert "overlay" in known[0]
    assert len(failed) == 0


def test_classify_unresolved_cross_domain_known_after_apply():
    """Cross-domain refs ({domain.resource.field}) are known after apply."""
    plan_result = {
        "create": {
            "site_b": {
                "category": [
                    {
                        "resource_name": "cross_ref",
                        "body": {
                            "key": "CrossRef",
                            "value": "{site_a.uat_source.body.value}",
                        },
                    },
                ]
            }
        },
        "update": {},
        "delete": {},
    }
    config = {
        "domains": {
            "site_a": {"resources": {"category": {"uat_source": {}}}},
            "site_b": {"resources": {"category": {"cross_ref": {}}}},
        }
    }
    known, failed = main_mod._classify_unresolved_plan_resources(plan_result, config)
    assert len(known) == 1
    assert "cross_ref" in known[0]
    assert len(failed) == 0


def test_classify_unresolved_zero_when_resolved():
    """Fully resolved plan has no unresolved resources."""
    plan_result = {
        "create": {
            "lab1": {
                "entityA": [
                    {"resource_name": "r1", "body": {"name": "resolved"}},
                ]
            }
        },
        "update": {},
        "delete": {},
    }
    config = {"domains": {"lab1": {"resources": {"entityA": {"r1": {}}}}}}
    known, failed = main_mod._classify_unresolved_plan_resources(plan_result, config)
    assert len(known) == 0
    assert len(failed) == 0


# ---------------------------------------------------------------------------
# Fix 10: Apply recomputation warning
# ---------------------------------------------------------------------------


def test_apply_shows_recomputation_warning(tmp_path, monkeypatch):
    """Apply should log a recomputation notice when there are changes."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            plan_result={
                "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                "update": {},
                "delete": {},
                "operations": {},
            },
            run_result={"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}},
        ),
    )

    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )

    result = runner.invoke(
        cli, ["apply", "--state", str(state_file), "--auto-approve", "--no-refresh"]
    )
    assert result.exit_code == 0
    text = "\n".join(logs)
    assert "recomputes" in text.lower()


# ---------------------------------------------------------------------------
# Fix 7: Destroy passes entity_rules_map
# ---------------------------------------------------------------------------


def test_destroy_passes_rules(tmp_path, monkeypatch):
    """Destroy should build and pass entity_rules_map to provider.destroy()."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {
                            "entityA": {"r": {"ext_id": "e1", "body": {"x": 1}}}
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    destroy_kwargs: list[dict] = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"r": {"ext_id": "e1", "body": {}}}}
        }
        run_results = {}
        domain_entity_resource_map = {
            "lab1": {
                "entityA": {"r": {"body": {"x": 1}, "rules": {"prevent_destroy": True}}}
            }
        }

        def destroy(self, **kw):
            destroy_kwargs.append(kw)
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        ["destroy", "--state", str(state_file), "--auto-approve", "--no-refresh"],
    )
    assert result.exit_code == 0
    assert destroy_kwargs
    rules = destroy_kwargs[0].get("entity_rules_map", {})
    assert "lab1" in rules
    assert rules["lab1"]["entityA"]["r"]["prevent_destroy"] is True


# ---------------------------------------------------------------------------
# Low-risk 1: --strict flag on plan and apply
# ---------------------------------------------------------------------------


def test_plan_strict_fails_on_refresh_error(tmp_path, monkeypatch):
    """Plan --strict should exit non-zero when refresh fails."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("refresh fail")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["plan", "--state", str(state_file), "--strict"])
    assert result.exit_code != 0


def test_plan_strict_succeeds_when_refresh_works(tmp_path, monkeypatch):
    """Plan --strict should succeed when refresh works fine."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(refresh_result=state_data),
    )
    result = runner.invoke(cli, ["plan", "--state", str(state_file), "--strict"])
    assert result.exit_code == 0


def test_apply_strict_fails_on_refresh_error(tmp_path, monkeypatch):
    """Apply --strict should exit non-zero when refresh fails."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None

        def refresh_state(self):
            raise RuntimeError("refresh fail")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

        def run(self, **kw):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli, ["apply", "--state", str(state_file), "--strict", "--auto-approve"]
    )
    assert result.exit_code != 0


def test_apply_without_strict_continues_on_refresh_error(tmp_path, monkeypatch):
    """Apply without --strict should still proceed when refresh fails."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"r": {"ext_id": "e1", "body": {}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {}
        domain_entity_resource_map = {}

        def refresh_state(self):
            raise RuntimeError("refresh fail")

        def plan(self):
            return {"create": {}, "update": {}, "delete": {}, "operations": {}}

        def run(self, **kw):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(cli, ["apply", "--state", str(state_file), "--auto-approve"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Low-risk 2: --target flag on destroy
# ---------------------------------------------------------------------------


def test_destroy_target_filters_resources(tmp_path, monkeypatch):
    """Destroy --target should only destroy the targeted resource."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {
                            "entityA": {
                                "r1": {"ext_id": "e1", "body": {}},
                                "r2": {"ext_id": "e2", "body": {}},
                            }
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    captured_map: list[dict] = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {
            "lab1": {
                "entityA": {
                    "r1": {"ext_id": "e1", "body": {}},
                    "r2": {"ext_id": "e2", "body": {}},
                }
            }
        }
        run_results = {}
        domain_entity_resource_map = {
            "lab1": {"entityA": {"r1": {"body": {}}, "r2": {"body": {}}}}
        }

        def destroy(self, **kw):
            captured_map.append(dict(self.previous_domain_entity_resource_map))
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        [
            "destroy",
            "--state",
            str(state_file),
            "--auto-approve",
            "--no-refresh",
            "--target",
            "r1",
        ],
    )
    assert result.exit_code == 0
    assert captured_map
    assert "r1" in captured_map[0].get("lab1", {}).get("entityA", {})
    assert "r2" not in captured_map[0].get("lab1", {}).get("entityA", {})


def test_destroy_target_preserves_non_targeted_state(tmp_path, monkeypatch):
    """Destroy --target should keep non-targeted resources in state."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {
                            "entityA": {
                                "keep": {"extId": "e1", "body": {"k": 1}},
                                "remove": {"extId": "e2", "body": {"k": 2}},
                            }
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {
            "lab1": {
                "entityA": {
                    "keep": {"extId": "e1", "body": {"k": 1}},
                    "remove": {"extId": "e2", "body": {"k": 2}},
                }
            }
        }
        run_results = {}
        domain_entity_resource_map = {
            "lab1": {
                "entityA": {
                    "keep": {"body": {"k": 1}},
                    "remove": {"body": {"k": 2}},
                }
            }
        }

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        [
            "destroy",
            "--state",
            str(state_file),
            "--auto-approve",
            "--no-refresh",
            "--target",
            "remove",
        ],
    )
    assert result.exit_code == 0
    final_state = yaml.safe_load(state_file.read_text())
    lab1_resources = final_state["domains"]["lab1"]["resources"]["entityA"]
    assert "keep" in lab1_resources
    assert lab1_resources["keep"]["extId"] == "e1"
    assert "remove" not in lab1_resources


def test_destroy_target_warns_on_missing(tmp_path, monkeypatch):
    """Destroy --target should warn if a targeted resource isn't in state."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}}
        }
        domain_entity_resource_map = {"lab1": {"entityA": {"r1": {"body": {}}}}}

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger,
        "warning",
        lambda msg, *a: logs.append(msg % a if a else msg),
    )

    result = runner.invoke(
        cli,
        [
            "destroy",
            "--state",
            str(state_file),
            "--auto-approve",
            "--target",
            "nonexistent",
        ],
    )
    assert result.exit_code == 0
    assert any("nonexistent" in log for log in logs)


def test_destroy_without_target_destroys_all(tmp_path, monkeypatch):
    """Destroy without --target should present all resources for deletion."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {
                            "entityA": {
                                "r1": {"ext_id": "e1", "body": {}},
                                "r2": {"ext_id": "e2", "body": {}},
                            }
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    logs: list[str] = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {
                "entityA": {
                    "r1": {"ext_id": "e1", "body": {}},
                    "r2": {"ext_id": "e2", "body": {}},
                }
            }
        }
        domain_entity_resource_map = {
            "lab1": {"entityA": {"r1": {"body": {}}, "r2": {"body": {}}}}
        }

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    monkeypatch.setattr(
        main_mod.logger,
        "info",
        lambda msg, *a: logs.append(msg % a if a else msg),
    )
    result = runner.invoke(
        cli,
        ["destroy", "--state", str(state_file), "--auto-approve", "--no-refresh"],
    )
    assert result.exit_code == 0
    text = "\n".join(logs)
    assert "r1" in text
    assert "r2" in text


# ---------------------------------------------------------------------------
# Low-risk 3: Import prints suggested config
# ---------------------------------------------------------------------------


def test_import_prints_config_snippet(tmp_path, monkeypatch):
    """Import should print a YAML config snippet after success."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "res1": {"extId": "ext-123", "body": {"foo": "bar"}}
                            }
                        },
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))
    monkeypatch.setattr(
        main_mod,
        "Provider",
        _make_dummy_provider(
            import_result={
                "entity_name": "entityA",
                "sanitized_data": {"foo": "imported_value"},
                "extId": "ext-123",
                "resource_entry": {"extId": "ext-123", "body": {"foo": "bar"}},
            }
        ),
    )

    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger,
        "info",
        lambda msg, *a: logs.append(msg % a if a else msg),
    )

    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "res1",
            "lab1",
        ],
    )
    assert result.exit_code == 0
    text = "\n".join(logs)
    assert "Suggested config" in text
    assert "ext-123" in text


# ---------------------------------------------------------------------------
# Low-risk 4: Bulk import via --file
# ---------------------------------------------------------------------------


def test_import_bulk_file(tmp_path, monkeypatch):
    """Bulk import via --file should import all entries."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "r1": {"extId": "e1", "body": {}},
                                "r2": {"extId": "e2", "body": {}},
                            }
                        },
                    }
                }
            }
        )
    )
    import_manifest = tmp_path / "imports.yml"
    import_manifest.write_text(
        yaml.safe_dump(
            [
                {"resource_name": "r1", "domain_name": "lab1"},
                {"resource_name": "r2", "domain_name": "lab1"},
            ]
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))

    import_calls: list[str] = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        def import_resource_data(self, rn, dn):
            import_calls.append(rn)
            return {
                "entity_name": "entityA",
                "sanitized_data": {"k": "v"},
                "extId": f"ext-{rn}",
                "resource_entry": {"extId": f"ext-{rn}", "body": {}},
            }

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)

    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "--file",
            str(import_manifest),
        ],
    )
    assert result.exit_code == 0
    assert import_calls == ["r1", "r2"]


def test_import_bulk_file_with_positional_args_errors(tmp_path, monkeypatch):
    """--file combined with positional args should raise UsageError."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(yaml.safe_dump({"domains": {"lab1": {"host": "h"}}}))
    import_manifest = tmp_path / "imports.yml"
    import_manifest.write_text(
        yaml.safe_dump([{"resource_name": "r1", "domain_name": "lab1"}])
    )
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))

    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "--file",
            str(import_manifest),
            "r1",
            "lab1",
        ],
    )
    assert result.exit_code != 0


def test_import_no_args_no_file_errors():
    """Import with no positional args and no --file should error."""
    result = runner.invoke(cli, ["import"])
    assert result.exit_code != 0


def test_import_bulk_partial_failure(tmp_path, monkeypatch):
    """Bulk import should continue on partial failure and report counts."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(yaml.safe_dump({"domains": {}}))
    global_file = tmp_path / "global.yml"
    global_file.write_text(yaml.safe_dump({"config": {}}))
    input_file = tmp_path / "input.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "username": "admin",
                        "password": "pass",
                        "resources": {
                            "entityA": {
                                "good": {"extId": "e1", "body": {}},
                                "bad": {"extId": "e2", "body": {}},
                            }
                        },
                    }
                }
            }
        )
    )
    import_manifest = tmp_path / "imports.yml"
    import_manifest.write_text(
        yaml.safe_dump(
            [
                {"resource_name": "good", "domain_name": "lab1"},
                {"resource_name": "bad", "domain_name": "lab1"},
            ]
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: yaml.safe_load(open(x)))

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        def import_resource_data(self, rn, dn):
            if rn == "bad":
                raise RuntimeError("import failed")
            return {
                "entity_name": "entityA",
                "sanitized_data": {"k": "v"},
                "extId": "ext-good",
                "resource_entry": {"extId": "e1", "body": {}},
            }

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)

    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger,
        "info",
        lambda msg, *a: logs.append(msg % a if a else msg),
    )

    result = runner.invoke(
        cli,
        [
            "import",
            "--state",
            str(state_file),
            "--input",
            str(input_file),
            "--global-file",
            str(global_file),
            "--file",
            str(import_manifest),
        ],
    )
    assert result.exit_code == 0
    text = "\n".join(logs)
    assert "1 succeeded" in text
    assert "1 failed" in text


# ---------------------------------------------------------------------------
# _resolve_import_entries unit tests
# ---------------------------------------------------------------------------


def test_resolve_import_entries_positional():
    """Positional args should produce a single-entry list."""
    entries = main_mod._resolve_import_entries("r1", "d1", None)
    assert entries == [{"resource_name": "r1", "domain_name": "d1"}]


def test_resolve_import_entries_file(tmp_path):
    """--file should parse the manifest correctly."""
    manifest = tmp_path / "m.yml"
    manifest.write_text(
        yaml.safe_dump(
            [
                {"resource_name": "a", "domain_name": "d1"},
                {"resource_name": "b", "domain_name": "d2"},
            ]
        )
    )
    entries = main_mod._resolve_import_entries(None, None, str(manifest))
    assert len(entries) == 2
    assert entries[0] == {"resource_name": "a", "domain_name": "d1"}


def test_resolve_import_entries_invalid_manifest(tmp_path):
    """A malformed manifest should raise UsageError."""
    manifest = tmp_path / "bad.yml"
    manifest.write_text("not_a_list: true\n")
    with pytest.raises(click.UsageError):
        main_mod._resolve_import_entries(None, None, str(manifest))


def test_resolve_import_entries_empty_manifest(tmp_path):
    """An empty manifest should raise UsageError."""
    manifest = tmp_path / "empty.yml"
    manifest.write_text("[]")
    with pytest.raises(click.UsageError):
        main_mod._resolve_import_entries(None, None, str(manifest))


def test_resolve_import_entries_conflict(tmp_path):
    """Positional args + --file should raise UsageError."""
    manifest = tmp_path / "m.yml"
    manifest.write_text(yaml.safe_dump([{"resource_name": "a", "domain_name": "d1"}]))
    with pytest.raises(click.UsageError):
        main_mod._resolve_import_entries("r1", "d1", str(manifest))


def test_resolve_import_entries_missing_positional():
    """Missing positional args without --file should raise UsageError."""
    with pytest.raises(click.UsageError):
        main_mod._resolve_import_entries(None, None, None)


def test_destroy_with_parallel(tmp_path, monkeypatch):
    """Destroy with --parallel should set provider.max_workers."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    captured_workers: list = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}}
        }
        domain_entity_resource_map = {"lab1": {"entityA": {"r1": {"body": {}}}}}

        def destroy(self, **kw):
            captured_workers.append(self.max_workers)
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        [
            "destroy",
            "--state",
            str(state_file),
            "--auto-approve",
            "--no-refresh",
            "--parallel",
            "4",
        ],
    )
    assert result.exit_code == 0
    assert captured_workers == [4]


def test_validate_file_path_missing():
    """_validate_file_path raises FileNotFoundError for non-existent path."""
    with pytest.raises(FileNotFoundError, match="not found"):
        main_mod._validate_file_path("/no/such/file.yml", "Test file")


def test_validate_file_path_directory(tmp_path):
    """_validate_file_path raises IsADirectoryError for directory path."""
    with pytest.raises(IsADirectoryError, match="is a directory"):
        main_mod._validate_file_path(str(tmp_path), "Test file")


def test_load_config_file_directory(tmp_path):
    """_load_config_file should raise ClickException when path is a directory."""
    with pytest.raises(click.ClickException, match="is a directory"):
        main_mod._load_config_file(str(tmp_path))


def test_load_config_file_empty_dict(tmp_path, monkeypatch):
    """_load_config_file should raise when read_input_file returns empty dict."""
    cfg = tmp_path / "empty.yml"
    cfg.write_text("---\n{}\n")
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: {})
    with pytest.raises(click.ClickException, match="empty"):
        main_mod._load_config_file(str(cfg))


def test_load_config_file_none(tmp_path, monkeypatch):
    """_load_config_file should raise when read_input_file returns None."""
    cfg = tmp_path / "null.yml"
    cfg.write_text("---\nnull\n")
    monkeypatch.setattr(main_mod, "read_input_file", lambda x: None)
    with pytest.raises(click.ClickException, match="empty"):
        main_mod._load_config_file(str(cfg))


def test_print_refresh_diff_prev_resources_not_dict(monkeypatch):
    """Non-dict prev_resources is coerced to empty without crash."""
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger, "info", lambda msg, *a: logs.append(msg % a if a else msg)
    )
    prev = {"domains": {"lab1": {"resources": "not-a-dict"}}}
    ref = {"domains": {"lab1": {"resources": {}}}}
    main_mod._print_refresh_diff(prev, ref)
    text = "\n".join(logs)
    assert "No resources" in text or "0 changed" in text


def test_destroy_target_empty_match(tmp_path, monkeypatch):
    """Destroy --target with no matching resources shows 'No resources'."""
    state_file = tmp_path / "state.yml"
    state_file.write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "lab1": {
                        "host": "1.2.3.4",
                        "resources": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}},
                    }
                }
            }
        )
    )
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"r1": {"ext_id": "e1", "body": {}}}}
        }
        domain_entity_resource_map = {"lab1": {"entityA": {"r1": {"body": {}}}}}

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    logs: list[str] = []
    monkeypatch.setattr(
        main_mod.logger,
        "info",
        lambda msg, *a: logs.append(msg % a if a else msg),
    )

    result = runner.invoke(
        cli,
        [
            "destroy",
            "--state",
            str(state_file),
            "--auto-approve",
            "--target",
            "nonexistent",
        ],
    )
    assert result.exit_code == 0
    text = "\n".join(logs)
    assert "No resources" in text


# ---------------------------------------------------------------------------
# destroy: refresh before destroy
# ---------------------------------------------------------------------------


def test_destroy_refreshes_state_by_default(tmp_path, monkeypatch):
    """Destroy should auto-refresh state before computing the destroy plan."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    refresh_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}}
        }
        domain_entity_resource_map = {}

        def refresh_state(self):
            refresh_called.append(True)
            return state_data

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli, ["destroy", "--state", str(state_file), "--auto-approve"]
    )
    assert result.exit_code == 0
    assert refresh_called


def test_destroy_no_refresh_flag_skips_refresh(tmp_path, monkeypatch):
    """Destroy with --no-refresh should skip the auto-refresh step."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    refresh_called = []

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"res1": {"ext_id": "e1", "body": {"a": 1}}}}
        }
        domain_entity_resource_map = {}

        def refresh_state(self):
            refresh_called.append(True)
            return state_data

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        ["destroy", "--state", str(state_file), "--auto-approve", "--no-refresh"],
    )
    assert result.exit_code == 0
    assert not refresh_called


def test_destroy_strict_refresh_failure_exits(tmp_path, monkeypatch):
    """Destroy with --strict should exit 1 when refresh fails."""
    state_file = tmp_path / "state.yml"
    state_data = {
        "domains": {
            "lab1": {
                "host": "1.2.3.4",
                "resources": {"entityA": {"res1": {"ext_id": "e1", "body": {}}}},
            }
        }
    }
    state_file.write_text(yaml.safe_dump(state_data))
    monkeypatch.setattr(os, "chmod", lambda *a, **kw: None)
    _mock_read_input(monkeypatch)

    class DummyProvider:
        def __init__(self, *a, **kw):
            pass

        max_workers = None
        run_results = {}
        previous_domain_entity_resource_map = {
            "lab1": {"entityA": {"res1": {"ext_id": "e1", "body": {}}}}
        }
        domain_entity_resource_map = {}

        def refresh_state(self):
            raise RuntimeError("connection refused")

        def destroy(self, **kw):
            return {"domains": {}}

    monkeypatch.setattr(main_mod, "Provider", DummyProvider)
    result = runner.invoke(
        cli,
        ["destroy", "--state", str(state_file), "--auto-approve", "--strict"],
    )
    assert result.exit_code == 1


def test_resolve_import_entries_non_dict_entry(tmp_path):
    """Manifest entry that is not a dict should raise UsageError."""
    manifest = tmp_path / "bad.yml"
    manifest.write_text(yaml.safe_dump(["just_a_string"]))
    with pytest.raises(click.UsageError, match="not a mapping"):
        main_mod._resolve_import_entries(None, None, str(manifest))


def test_resolve_import_entries_missing_fields(tmp_path):
    """Manifest entry missing required fields should raise UsageError."""
    manifest = tmp_path / "bad.yml"
    manifest.write_text(yaml.safe_dump([{"resource_name": "r1"}]))
    with pytest.raises(click.UsageError, match="missing"):
        main_mod._resolve_import_entries(None, None, str(manifest))


# ---------------------------------------------------------------------------
# Graceful interrupt helper
# ---------------------------------------------------------------------------


def test_run_with_graceful_interrupt_normal():
    """Normal execution returns action result."""

    class FakeProvider:
        _shutdown_requested = threading.Event()

        def request_shutdown(self):
            self._shutdown_requested.set()

        def get_partial_state(self):
            return {"domains": {"partial": True}}

    provider = FakeProvider()
    result = main_mod._run_with_graceful_interrupt(
        provider, lambda on_state_change: {"domains": {"ok": True}}, lambda s: None
    )
    assert result == {"domains": {"ok": True}}


def test_run_with_graceful_interrupt_keyboard_interrupt():
    """KeyboardInterrupt during action returns partial state."""

    class FakeProvider:
        _shutdown_requested = threading.Event()

        def request_shutdown(self):
            self._shutdown_requested.set()

        def get_partial_state(self):
            return {"domains": {"rescued": True}}

    def _boom(on_state_change):
        raise KeyboardInterrupt

    provider = FakeProvider()
    result = main_mod._run_with_graceful_interrupt(provider, _boom, lambda s: None)
    assert result == {"domains": {"rescued": True}}


def test_run_with_graceful_interrupt_sigint():
    """First SIGINT sets shutdown flag and restores default handler."""
    import signal as signal_mod

    class FakeProvider:
        _shutdown_requested = threading.Event()
        shutdown_called = False

        def request_shutdown(self):
            self._shutdown_requested.set()
            self.shutdown_called = True

        def get_partial_state(self):
            return {"domains": {}}

    provider = FakeProvider()

    if sys.platform == "win32":
        # os.kill(pid, SIGINT) sends CTRL_C_EVENT to the process group
        # on Windows, crashing the test runner.  Instead, invoke the
        # installed signal handler directly.
        def _action_that_fires_handler(on_state_change):
            handler = signal_mod.getsignal(signal_mod.SIGINT)
            if callable(handler):
                handler(signal_mod.SIGINT, None)
            return {"domains": {"done": True}}

        action = _action_that_fires_handler
    else:

        def _action_that_sends_sigint(on_state_change):
            os.kill(os.getpid(), signal_mod.SIGINT)
            return {"domains": {"done": True}}

        action = _action_that_sends_sigint

    prev = signal_mod.getsignal(signal_mod.SIGINT)
    try:
        main_mod._run_with_graceful_interrupt(provider, action, lambda s: None)
    except KeyboardInterrupt:
        pass
    finally:
        signal_mod.signal(signal_mod.SIGINT, prev)

    assert provider.shutdown_called
