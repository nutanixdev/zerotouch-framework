"""Tests for ``ztf.plan_file`` and the ``--out`` / ``--plan`` flags.

Covers Phase E item E2 (saved plan file with hash-pinned consistency
guard between ``ztf plan`` and ``ztf apply``).
"""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import orjson
import pytest
import yaml
from click.testing import CliRunner

import ztf.main as main_mod
from ztf.main import cli
from ztf.plan_file import (
    PLAN_FILE_SCHEMA_VERSION,
    PlanFileError,
    hash_input_config,
    hash_payload,
    read_plan_file,
    verify_plan_file,
    write_plan_file,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


class TestHashPayload:
    def test_hash_is_stable_for_equal_payloads(self) -> None:
        a = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
        b = {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}
        assert hash_payload(a) == hash_payload(b)

    def test_hash_changes_when_payload_changes(self) -> None:
        baseline = hash_payload({"a": 1})
        assert hash_payload({"a": 2}) != baseline
        assert hash_payload({"a": 1, "b": None}) != baseline

    def test_hash_handles_non_jsonable_values(self) -> None:
        # ``Path`` objects are common in resolved configs (template
        # paths). orjson's ``default=str`` lets them hash without raise.
        hash_payload({"p": Path("/tmp/x")})


class TestHashInputConfig:
    def test_excludes_functions_field(self) -> None:
        # ``functions`` carries live Python callables whose ``repr``
        # contains the memory address; including it would make the
        # plan-file hash non-deterministic across CLI invocations.
        a = {"domains": {"d": {}}, "functions": {"pad": lambda x: x}}
        b = {"domains": {"d": {}}, "functions": {"pad": lambda x: x}}
        assert hash_input_config(a) == hash_input_config(b)

    def test_includes_other_fields(self) -> None:
        a = {"domains": {"d": {"host": "1.1.1.1"}}}
        b = {"domains": {"d": {"host": "9.9.9.9"}}}
        assert hash_input_config(a) != hash_input_config(b)

    def test_non_dict_payload_falls_through_to_hash_payload(self) -> None:
        assert hash_input_config([1, 2, 3]) == hash_payload([1, 2, 3])


# ---------------------------------------------------------------------------
# write/read round-trip
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_plan() -> dict[str, object]:
    return {
        "create": {"lab1": {"vm": [{"resource_name": "v1"}]}},
        "update": {},
        "delete": {},
        "operations": {},
    }


@pytest.fixture
def sample_input() -> dict[str, object]:
    return {"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}}


@pytest.fixture
def sample_state() -> dict[str, object]:
    return {"domains": {"lab1": {"host": "1.2.3.4", "resources": {}}}}


class TestPlanFileRoundTrip:
    def test_round_trip_preserves_fields(
        self,
        tmp_path: Path,
        sample_plan: dict[str, object],
        sample_input: dict[str, object],
        sample_state: dict[str, object],
    ) -> None:
        path = tmp_path / "plan.json"
        ts = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
        written = write_plan_file(
            path,
            operations=sample_plan,
            input_config=sample_input,
            state_data=sample_state,
            created_at=ts,
        )
        loaded = read_plan_file(path)
        assert loaded.schema_version == PLAN_FILE_SCHEMA_VERSION
        assert loaded.input_hash == written.input_hash == hash_payload(sample_input)
        assert loaded.state_hash == written.state_hash == hash_payload(sample_state)
        assert loaded.operations == sample_plan
        assert loaded.created_at == ts.isoformat()

    def test_plan_file_round_trip_is_byte_identical(
        self,
        tmp_path: Path,
        sample_plan: dict[str, object],
        sample_input: dict[str, object],
        sample_state: dict[str, object],
    ) -> None:
        ts = datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc)
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        write_plan_file(
            a,
            operations=sample_plan,
            input_config=sample_input,
            state_data=sample_state,
            created_at=ts,
        )
        write_plan_file(
            b,
            operations=sample_plan,
            input_config=sample_input,
            state_data=sample_state,
            created_at=ts,
        )
        assert a.read_bytes() == b.read_bytes()

    def test_write_creates_parent_directories(
        self,
        tmp_path: Path,
        sample_plan: dict[str, object],
        sample_input: dict[str, object],
        sample_state: dict[str, object],
    ) -> None:
        path = tmp_path / "deeply" / "nested" / "plan.json"
        write_plan_file(
            path,
            operations=sample_plan,
            input_config=sample_input,
            state_data=sample_state,
        )
        assert path.is_file()


class TestReadPlanFileErrors:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PlanFileError, match="not found"):
            read_plan_file(tmp_path / "nope.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_bytes(b"{not json")
        with pytest.raises(PlanFileError, match="not valid JSON"):
            read_plan_file(path)

    def test_non_object_top_level_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_bytes(b"[1, 2, 3]")
        with pytest.raises(PlanFileError, match="JSON object"):
            read_plan_file(path)

    def test_missing_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "incomplete.json"
        path.write_bytes(orjson.dumps({"schema_version": 1}))
        with pytest.raises(PlanFileError, match="missing required field"):
            read_plan_file(path)

    def test_schema_version_mismatch_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "future.json"
        path.write_bytes(
            orjson.dumps(
                {
                    "schema_version": PLAN_FILE_SCHEMA_VERSION + 99,
                    "ztf_version": "9.9.9",
                    "created_at": "2026-04-17T00:00:00+00:00",
                    "input_hash": "x",
                    "state_hash": "y",
                    "operations": {},
                }
            )
        )
        with pytest.raises(PlanFileError, match="schema_version"):
            read_plan_file(path)

    def test_non_object_operations_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad_ops.json"
        path.write_bytes(
            orjson.dumps(
                {
                    "schema_version": PLAN_FILE_SCHEMA_VERSION,
                    "ztf_version": "x",
                    "created_at": "x",
                    "input_hash": "x",
                    "state_hash": "x",
                    "operations": [1, 2],
                }
            )
        )
        with pytest.raises(PlanFileError, match="non-object 'operations'"):
            read_plan_file(path)


# ---------------------------------------------------------------------------
# Verification (hash drift detection)
# ---------------------------------------------------------------------------


class TestVerifyPlanFile:
    def _plan(
        self,
        tmp_path: Path,
        input_config: dict,
        state_data: dict,
    ):
        path = tmp_path / "plan.json"
        write_plan_file(
            path,
            operations={"create": {}, "update": {}, "delete": {}, "operations": {}},
            input_config=input_config,
            state_data=state_data,
            created_at=datetime(2026, 4, 17, 12, 0, 0, tzinfo=timezone.utc),
        )
        return read_plan_file(path)

    def test_no_drift_returns_empty_list(self, tmp_path: Path) -> None:
        cfg = {"a": 1}
        st = {"b": 2}
        plan = self._plan(tmp_path, cfg, st)
        assert verify_plan_file(plan, current_input=cfg, current_state=st) == []

    def test_input_hash_mismatch_blocks_apply_without_force(
        self, tmp_path: Path
    ) -> None:
        plan = self._plan(tmp_path, {"a": 1}, {"b": 2})
        with pytest.raises(PlanFileError, match="Input config hash drift"):
            verify_plan_file(plan, current_input={"a": 999}, current_state={"b": 2})

    def test_state_hash_mismatch_blocks_apply_without_force(
        self, tmp_path: Path
    ) -> None:
        plan = self._plan(tmp_path, {"a": 1}, {"b": 2})
        with pytest.raises(PlanFileError, match="State hash drift"):
            verify_plan_file(plan, current_input={"a": 1}, current_state={"b": 999})

    def test_both_hashes_mismatch_lists_both(self, tmp_path: Path) -> None:
        plan = self._plan(tmp_path, {"a": 1}, {"b": 2})
        with pytest.raises(PlanFileError) as info:
            verify_plan_file(plan, current_input={"a": 9}, current_state={"b": 9})
        msg = str(info.value)
        assert "Input config hash drift" in msg
        assert "State hash drift" in msg

    def test_force_returns_drift_without_raising(self, tmp_path: Path) -> None:
        plan = self._plan(tmp_path, {"a": 1}, {"b": 2})
        drift = verify_plan_file(
            plan,
            current_input={"a": 9},
            current_state={"b": 2},
            force=True,
        )
        assert len(drift) == 1
        assert "Input config hash drift" in drift[0]


# ---------------------------------------------------------------------------
# CLI integration: plan --out, apply --plan, --force
# ---------------------------------------------------------------------------


def _global_config() -> dict[str, object]:
    return {"config": {"debug": False}}


def _input_config(resources: dict | None = None) -> dict[str, object]:
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


def _mock_read_input(monkeypatch, *, input_data: dict | None = None) -> None:
    # ``load_config`` mutates the input dict (expanded resources are
    # written back).  Return a fresh deepcopy on every call so each
    # CLI invocation sees an unmutated, byte-identical input -- which
    # is what real callers experience when reading from disk.
    g = _global_config()
    i = input_data if input_data is not None else _input_config()

    def _read(x):
        return deepcopy(g) if "global" in x else deepcopy(i)

    def _load(path):
        return _read(path)

    monkeypatch.setattr(main_mod, "read_input_file", _read)
    monkeypatch.setattr(main_mod, "_load_config_file", _load)


def _make_provider(plan_calls: list[int], plan_result: dict, run_result: dict):
    class DummyProvider:
        def __init__(self, *a, **kw):
            self._shutdown_requested = threading.Event()

        max_workers = None
        previous_domain_entity_resource_map: dict = {}
        domain_entity_resource_map: dict = {}
        run_results: dict = {}

        def plan(self):
            plan_calls.append(1)
            return plan_result

        def run(self, **kw):
            return run_result

        def refresh_state(self):
            return {"domains": {}}

        def resolve_outputs(self):
            return {}

        def request_shutdown(self):
            self._shutdown_requested.set()

        def get_partial_state(self):
            return {"domains": {}}

    return DummyProvider


class TestCliPlanFileFlow:
    def test_plan_out_writes_file_with_hashes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))
        plan_path = tmp_path / "plan.json"

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        plan_calls: list[int] = []
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(
                plan_calls,
                plan_result={
                    "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                    "update": {},
                    "delete": {},
                    "operations": {},
                },
                run_result={"domains": {}},
            ),
        )

        result = runner.invoke(
            cli,
            [
                "plan",
                "--state",
                str(state_file),
                "--no-refresh",
                "--out",
                str(plan_path),
            ],
        )
        assert result.exit_code == 0, result.output
        assert plan_path.is_file()
        loaded = read_plan_file(plan_path)
        assert loaded.input_hash
        assert loaded.state_hash

    def test_apply_with_plan_file_skips_recomputation(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))
        plan_path = tmp_path / "plan.json"

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        plan_calls: list[int] = []
        plan_result = {
            "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
            "update": {},
            "delete": {},
            "operations": {},
        }
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(plan_calls, plan_result, {"domains": {}}),
        )

        plan_result_run = runner.invoke(
            cli,
            [
                "plan",
                "--state",
                str(state_file),
                "--no-refresh",
                "--out",
                str(plan_path),
            ],
        )
        assert plan_result_run.exit_code == 0, plan_result_run.output
        assert len(plan_calls) == 1, "plan() called during plan phase"

        apply_result = runner.invoke(
            cli,
            [
                "apply",
                "--state",
                str(state_file),
                "--no-refresh",
                "--auto-approve",
                "--plan",
                str(plan_path),
            ],
        )
        assert apply_result.exit_code == 0, apply_result.output
        assert len(plan_calls) == 1, (
            "Provider.plan() must NOT be called during 'apply --plan' "
            "(plan-file operations are used instead)."
        )

    def test_apply_input_hash_drift_blocks_without_force(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))
        plan_path = tmp_path / "plan.json"

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        plan_calls: list[int] = []
        plan_result = {
            "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
            "update": {},
            "delete": {},
            "operations": {},
        }
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(plan_calls, plan_result, {"domains": {}}),
        )

        runner.invoke(
            cli,
            [
                "plan",
                "--state",
                str(state_file),
                "--no-refresh",
                "--out",
                str(plan_path),
            ],
        )

        _mock_read_input(
            monkeypatch,
            input_data=_input_config(resources={"entityA": {"r": {"body": {"x": 99}}}}),
        )
        apply_result = runner.invoke(
            cli,
            [
                "apply",
                "--state",
                str(state_file),
                "--no-refresh",
                "--auto-approve",
                "--plan",
                str(plan_path),
            ],
        )
        # exit_code == 1 is the contract: drift detected, apply blocked.
        # Message text is verified at unit level in TestVerifyPlanFile.
        assert apply_result.exit_code == 1

    def test_apply_state_hash_drift_blocks_without_force(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))
        plan_path = tmp_path / "plan.json"

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        plan_calls: list[int] = []
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(
                plan_calls,
                {
                    "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                    "update": {},
                    "delete": {},
                    "operations": {},
                },
                {"domains": {}},
            ),
        )

        runner.invoke(
            cli,
            [
                "plan",
                "--state",
                str(state_file),
                "--no-refresh",
                "--out",
                str(plan_path),
            ],
        )

        state_file.write_text(
            yaml.safe_dump({"domains": {"lab1": {"host": "9.9.9.9", "resources": {}}}})
        )
        apply_result = runner.invoke(
            cli,
            [
                "apply",
                "--state",
                str(state_file),
                "--no-refresh",
                "--auto-approve",
                "--plan",
                str(plan_path),
            ],
        )
        assert apply_result.exit_code == 1

    def test_apply_with_force_proceeds_despite_drift(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))
        plan_path = tmp_path / "plan.json"

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        plan_calls: list[int] = []
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(
                plan_calls,
                {
                    "create": {"lab1": {"entityA": [{"resource_name": "r"}]}},
                    "update": {},
                    "delete": {},
                    "operations": {},
                },
                {"domains": {}},
            ),
        )

        runner.invoke(
            cli,
            [
                "plan",
                "--state",
                str(state_file),
                "--no-refresh",
                "--out",
                str(plan_path),
            ],
        )

        _mock_read_input(
            monkeypatch,
            input_data=_input_config(resources={"entityA": {"r": {"body": {"x": 42}}}}),
        )
        apply_result = runner.invoke(
            cli,
            [
                "apply",
                "--state",
                str(state_file),
                "--no-refresh",
                "--auto-approve",
                "--plan",
                str(plan_path),
                "--force",
            ],
        )
        assert apply_result.exit_code == 0, apply_result.output

    def test_apply_with_missing_plan_file_errors(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state_file = tmp_path / "state.yml"
        state_file.write_text(yaml.safe_dump({"domains": {}}))

        monkeypatch.setattr("os.chmod", lambda *a, **kw: None)
        _mock_read_input(monkeypatch)
        monkeypatch.setattr(
            main_mod,
            "Provider",
            _make_provider(
                [],
                {"create": {}, "update": {}, "delete": {}, "operations": {}},
                {"domains": {}},
            ),
        )

        result = runner.invoke(
            cli,
            [
                "apply",
                "--state",
                str(state_file),
                "--no-refresh",
                "--auto-approve",
                "--plan",
                str(tmp_path / "missing.json"),
            ],
        )
        assert result.exit_code == 1
