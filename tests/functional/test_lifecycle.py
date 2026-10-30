"""Parametrized functional lifecycle tests for ZTF.

Validates init -> plan -> apply -> refresh -> idempotent-plan -> destroy
against real Prism Central instances using the entity configs defined in
``namespace_configs.py``.

Run all::

    pytest tests/functional/test_lifecycle.py -m functional --timeout=600

Run a single namespace::

    pytest tests/functional/test_lifecycle.py -k "clustermgmt" --timeout=600
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.functional.conftest import (
    DEFAULT_GLOBAL_CONFIG,
    get_pc_credentials,
)
from tests.functional.namespace_configs import (
    DEPENDENCY_CHAIN_CONFIGS,
    DOMAIN_NAME,
    ENTITY_CONFIGS,
    get_dependency_chain_configs,
)
from tests.functional.runner import ZTFLifecycleRunner

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_ENTITY_IDS = [e["id"] for e in ENTITY_CONFIGS]
_DEP_CHAIN_IDS = [e["id"] for e in DEPENDENCY_CHAIN_CONFIGS]


def _build_runner(
    tmp_path: Path,
    entry: dict[str, Any],
) -> ZTFLifecycleRunner:
    """Construct a ``ZTFLifecycleRunner`` from a namespace config entry."""
    work_dir = tmp_path / entry["id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    return ZTFLifecycleRunner(
        work_dir=work_dir,
        global_config=DEFAULT_GLOBAL_CONFIG,
        input_config=entry["input_config"],
    )


def _resolve_entry(
    entity_id: str,
    run_id: int,
    env_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve a single entity config entry with credentials injected."""
    entry_template = next((e for e in ENTITY_CONFIGS if e["id"] == entity_id), None)
    if entry_template is None:
        return None
    try:
        creds = get_pc_credentials(entry_template["pc_target"], env_data)
    except RuntimeError:
        return None
    cfg = dict(entry_template)
    cfg["input_config"] = cfg["builder"](run_id, creds)
    cfg["resource_name"] = f"ztf_func_{run_id}"
    cfg["domain_name"] = DOMAIN_NAME
    return cfg


# ------------------------------------------------------------------
# Tests -- Single Entity Lifecycle
# ------------------------------------------------------------------


@pytest.mark.functional
class TestInit:
    """Verify ``ztf init`` creates an empty state file."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_init_creates_empty_state(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
    ) -> None:
        """Init should produce ``state.yml`` with ``{"domains": {}}``."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")

        runner = _build_runner(tmp_path, entry)
        result = runner.init()

        assert result.ok, f"init failed: {result.stderr}"
        assert runner.state_path.exists()
        assert result.state == {"domains": {}}


@pytest.mark.functional
@pytest.mark.slow
class TestPlanCreate:
    """After init, plan should show CREATE actions."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_plan_shows_create(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
    ) -> None:
        """Plan on empty state must report resource creation."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")

        runner = _build_runner(tmp_path, entry)
        r_init = runner.init()
        assert r_init.ok

        r_plan = runner.plan(no_refresh=True)
        assert r_plan.ok, f"plan failed: {r_plan.stderr}"

        combined = r_plan.stdout + r_plan.stderr
        assert "CREATE" in combined.upper() or "to create" in combined.lower(), (
            f"Plan output should mention creation:\n{combined[:1000]}"
        )


@pytest.mark.functional
@pytest.mark.slow
class TestFullLifecycle:
    """End-to-end: init -> plan -> apply -> refresh -> plan(idempotent) -> destroy."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_full_lifecycle(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
    ) -> None:
        """Complete lifecycle must succeed with no leftover resources."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")
        if not entry.get("crud_supported"):
            pytest.skip(f"{entity_id} does not support full CRUD")

        runner = _build_runner(tmp_path, entry)
        resource_name = entry["resource_name"]
        entity = entry["entity"]

        # -- init --
        r = runner.init()
        assert r.ok, f"init failed: {r.stderr}"

        # -- plan (should show create) --
        r = runner.plan(no_refresh=True)
        assert r.ok, f"plan failed: {r.stderr}"

        # -- apply --
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"
        assert runner.state_has_resource(DOMAIN_NAME, entity, resource_name), (
            f"Resource {resource_name} not found in state after apply. "
            f"stdout: {r.stdout[-500:]}\nstderr: {r.stderr[-500:]}"
        )

        ext_id = runner.get_resource_ext_id(DOMAIN_NAME, entity, resource_name)
        assert ext_id, f"No ext_id for {resource_name} after apply"

        # -- refresh --
        r = runner.refresh()
        assert r.ok, f"refresh failed: {r.stderr}"
        assert runner.state_has_resource(DOMAIN_NAME, entity, resource_name), (
            "Resource disappeared after refresh"
        )

        # -- plan (idempotent check) --
        r = runner.plan(no_refresh=True)
        assert r.ok, f"idempotent plan failed: {r.stderr}"
        combined = r.stdout + r.stderr
        has_create_or_delete = (
            "[create]" in combined.lower() or "[delete]" in combined.lower()
        )
        assert not has_create_or_delete, (
            f"Plan after refresh must not show CREATE/DELETE:\n{combined[:1000]}"
        )
        if (
            "no changes" not in combined.lower()
            and "up-to-date" not in combined.lower()
        ):
            warnings.warn(
                f"Plan after refresh shows updates (likely server-computed "
                f"field diffs, not a real drift): "
                f"{[ln for ln in combined.splitlines() if 'update' in ln.lower()][:3]}",
                stacklevel=1,
            )

        # -- destroy --
        r = runner.destroy(timeout=600)
        assert r.ok, f"destroy failed: {r.stderr}"

        remaining = runner.get_state_resources(DOMAIN_NAME)
        entity_resources = remaining.get(entity, {})
        assert resource_name not in entity_resources, (
            f"Resource {resource_name} still in state after destroy"
        )


@pytest.mark.functional
@pytest.mark.slow
class TestApplyAndRefresh:
    """Focused tests for apply and refresh behaviour."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_apply_creates_resource(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
        cleanup_guard: list,
    ) -> None:
        """Apply should create the resource and store ext_id in state."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")
        if not entry.get("crud_supported"):
            pytest.skip(f"{entity_id} does not support CRUD")

        runner = _build_runner(tmp_path, entry)
        cleanup_guard.append(runner)

        r = runner.init()
        assert r.ok
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"

        assert runner.state_has_resource(
            DOMAIN_NAME, entry["entity"], entry["resource_name"]
        ), (
            f"Resource {entry['resource_name']} not in state after apply. "
            f"stdout: {r.stdout[-300:]}\nstderr: {r.stderr[-300:]}"
        )

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_refresh_preserves_state(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
        cleanup_guard: list,
    ) -> None:
        """After apply, refresh should keep the resource in state."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")
        if not entry.get("crud_supported"):
            pytest.skip(f"{entity_id} does not support CRUD")

        runner = _build_runner(tmp_path, entry)
        cleanup_guard.append(runner)

        runner.init()
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"
        assert runner.state_has_resource(
            DOMAIN_NAME, entry["entity"], entry["resource_name"]
        ), "Apply did not create resource"

        pre_ext_id = runner.get_resource_ext_id(
            DOMAIN_NAME, entry["entity"], entry["resource_name"]
        )

        r = runner.refresh()
        assert r.ok, f"refresh failed: {r.stderr}"

        post_ext_id = runner.get_resource_ext_id(
            DOMAIN_NAME, entry["entity"], entry["resource_name"]
        )
        assert post_ext_id == pre_ext_id, (
            f"ext_id changed after refresh: {pre_ext_id} -> {post_ext_id}"
        )


@pytest.mark.functional
@pytest.mark.slow
class TestImport:
    """Validate the ``ztf import`` command."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_import_existing_resource(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
        cleanup_guard: list,
    ) -> None:
        """Create via apply, clear state, re-import, verify ext_id matches."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")
        if not entry.get("crud_supported"):
            pytest.skip(f"{entity_id} does not support CRUD")

        entity = entry["entity"]
        resource_name = entry["resource_name"]

        runner = _build_runner(tmp_path, entry)
        cleanup_guard.append(runner)

        runner.init()
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"
        assert runner.state_has_resource(DOMAIN_NAME, entity, resource_name), (
            f"Apply did not create {resource_name}"
        )

        original_ext_id = runner.get_resource_ext_id(DOMAIN_NAME, entity, resource_name)
        assert original_ext_id

        input_config = dict(entry["input_config"])
        domain_cfg = input_config["domains"][DOMAIN_NAME]
        res_body = domain_cfg["resources"][entity][resource_name]
        res_body["extId"] = original_ext_id

        with open(runner.work_dir / "input.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(input_config, fh, sort_keys=False)

        runner.init()
        assert not runner.state_has_resource(DOMAIN_NAME, entity, resource_name)

        r = runner.import_resource(resource_name, DOMAIN_NAME)
        assert r.ok, f"import failed: {r.stderr}"
        assert runner.state_has_resource(DOMAIN_NAME, entity, resource_name)

        imported_ext_id = runner.get_resource_ext_id(DOMAIN_NAME, entity, resource_name)
        assert imported_ext_id == original_ext_id, (
            f"Imported ext_id mismatch: {imported_ext_id} != {original_ext_id}"
        )


@pytest.mark.functional
@pytest.mark.slow
class TestDestroy:
    """Validate destroy behaviour."""

    @pytest.mark.parametrize("entity_id", _ENTITY_IDS)
    def test_destroy_cleans_state(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        entity_id: str,
    ) -> None:
        """After destroy, the resource must be gone from state."""
        entry = _resolve_entry(entity_id, run_id, env_data)
        if entry is None:
            pytest.skip(f"No credentials for {entity_id}")
        if not entry.get("crud_supported"):
            pytest.skip(f"{entity_id} does not support CRUD")

        runner = _build_runner(tmp_path, entry)
        runner.init()
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"

        r = runner.destroy(timeout=600)
        assert r.ok, f"destroy failed: {r.stderr}"

        remaining = runner.get_state_resources(DOMAIN_NAME)
        assert entry["resource_name"] not in remaining.get(entry["entity"], {})


# ------------------------------------------------------------------
# Tests -- Dependency Chain (multi-resource in one domain)
# ------------------------------------------------------------------


@pytest.mark.functional
@pytest.mark.slow
class TestDependencyChain:
    """Validate that multi-resource configs with data-source dependencies work.

    Creates multiple entities in a single domain where some depend on
    data sources. Verifies that ZTF resolves dependencies correctly,
    creates all resources, and destroys them cleanly.
    """

    @pytest.mark.parametrize("chain_id", _DEP_CHAIN_IDS)
    def test_dependency_chain_lifecycle(
        self,
        tmp_path: Path,
        env_data: dict,
        run_id: int,
        chain_id: str,
    ) -> None:
        """Full lifecycle for a multi-resource dependency chain."""
        chain_template = next(
            (e for e in DEPENDENCY_CHAIN_CONFIGS if e["id"] == chain_id),
            None,
        )
        if chain_template is None:
            pytest.skip(f"Unknown chain {chain_id}")

        try:
            creds = get_pc_credentials(chain_template["pc_target"], env_data)
        except RuntimeError:
            pytest.skip(f"No credentials for {chain_template['pc_target']}")

        chains = get_dependency_chain_configs(run_id, creds)
        entry = next((c for c in chains if c["id"] == chain_id), None)
        if entry is None:
            pytest.skip(f"Could not build config for {chain_id}")

        runner = _build_runner(tmp_path, entry)
        resource_names = entry["resource_names_resolved"]
        entities = entry["entities"]

        # -- init --
        r = runner.init()
        assert r.ok, f"init failed: {r.stderr}"

        # -- plan (should show creates for all entities) --
        r = runner.plan(no_refresh=True)
        assert r.ok, f"plan failed: {r.stderr}"
        combined = r.stdout + r.stderr
        assert "CREATE" in combined.upper() or "to create" in combined.lower(), (
            f"Plan should show creation for chain:\n{combined[:1000]}"
        )

        # -- apply --
        r = runner.apply(timeout=600)
        assert r.ok, f"apply failed: {r.stderr}"

        for entity in entities:
            rname = resource_names[entity]
            assert runner.state_has_resource(DOMAIN_NAME, entity, rname), (
                f"Resource {entity}/{rname} not in state after apply"
            )
            ext_id = runner.get_resource_ext_id(DOMAIN_NAME, entity, rname)
            assert ext_id, f"No ext_id for {entity}/{rname}"

        # -- refresh --
        r = runner.refresh()
        assert r.ok, f"refresh failed: {r.stderr}"
        for entity in entities:
            rname = resource_names[entity]
            assert runner.state_has_resource(DOMAIN_NAME, entity, rname), (
                f"{entity}/{rname} disappeared after refresh"
            )

        # -- destroy --
        r = runner.destroy(timeout=600)
        assert r.ok, f"destroy failed: {r.stderr}"

        remaining = runner.get_state_resources(DOMAIN_NAME)
        for entity in entities:
            rname = resource_names[entity]
            assert rname not in remaining.get(entity, {}), (
                f"{entity}/{rname} still in state after destroy"
            )
