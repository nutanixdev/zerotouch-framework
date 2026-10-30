"""Shared fixtures for ZTF functional tests.

Provides:
* ``env_config`` -- PC credentials loaded from env vars or ``env.json``.
* ``run_id`` -- unique per-session identifier for resource naming.
* ``work_dir`` -- isolated temp directory per test with auto-cleanup.
* ``lifecycle_runner`` -- factory fixture returning a ``ZTFLifecycleRunner``.
* ``cleanup_guard`` -- ensures ``destroy --auto-approve`` runs on teardown.
"""

from __future__ import annotations

import logging
import os
import random
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

try:
    import orjson

    def _load_json(path: str) -> dict:
        with open(path, "rb") as fh:
            return orjson.loads(fh.read())
except ImportError:
    import json

    def _load_json(path: str) -> dict:  # type: ignore[misc]
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)


from tests.functional.runner import ZTFLifecycleRunner

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GLOBAL_CONFIG: dict[str, Any] = {
    "config": {
        "port": 9440,
        "debug": False,
        "verify_ssl": False,
        "dry_run": False,
        "connect_timeout": 5000,
        "read_timeout": 300000,
    }
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_env_json() -> dict[str, Any]:
    """Load env.json from the repo root, returning empty dict on failure."""
    env_path = _REPO_ROOT / "env.json"
    if env_path.exists():
        return _load_json(str(env_path))
    return {}


def get_pc_credentials(
    alias: str, env_data: dict[str, Any] | None = None
) -> dict[str, str]:
    """Resolve PC credentials for *alias* from env vars or env.json.

    Env-var names follow the pattern ``<ALIAS_UPPER>_IP``,
    ``<ALIAS_UPPER>_USERNAME``, ``<ALIAS_UPPER>_PASSWORD``.
    Falls back to ``env.json`` keys like ``nested_7_5``,
    ``nested_7_5_username``, ``nested_7_5_password``.

    Args:
        alias: PC alias (e.g. ``"nested_7_5"``).
        env_data: Pre-loaded ``env.json`` dict (optional).

    Returns:
        Dict with ``host``, ``username``, ``password``.

    Raises:
        RuntimeError: When credentials cannot be resolved.
    """
    upper = alias.upper()
    host = os.environ.get(f"{upper}_IP")
    user = os.environ.get(f"{upper}_USERNAME")
    pwd = os.environ.get(f"{upper}_PASSWORD")

    if host and user and pwd:
        return {"host": host, "username": user, "password": pwd}

    if env_data is None:
        env_data = _load_env_json()

    host = host or env_data.get(alias)
    user = user or env_data.get(f"{alias}_username")
    pwd = pwd or env_data.get(f"{alias}_password")

    if not all((host, user, pwd)):
        raise RuntimeError(
            f"Cannot resolve credentials for PC alias '{alias}'. "
            f"Set {upper}_IP / {upper}_USERNAME / {upper}_PASSWORD env vars "
            f"or ensure env.json contains the keys."
        )
    return {"host": str(host), "username": str(user), "password": str(pwd)}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(scope="session")
def env_data() -> dict[str, Any]:
    """Load env.json once per session."""
    return _load_env_json()


@pytest.fixture(scope="session")
def run_id() -> int:
    """Unique numeric identifier for this test session."""
    return random.randint(10000, 99999)


@pytest.fixture()
def work_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a clean temp working directory; removed after the test."""
    wd = tmp_path / "ztf_work"
    wd.mkdir()
    yield wd
    shutil.rmtree(wd, ignore_errors=True)


@pytest.fixture()
def lifecycle_runner(work_dir: Path):
    """Factory fixture: returns a builder function for ``ZTFLifecycleRunner``.

    Usage in tests::

        runner = lifecycle_runner(input_config, variables={"pc_ip": "..."})
    """

    def _build(
        input_config: dict[str, Any],
        global_config: dict[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ZTFLifecycleRunner:
        return ZTFLifecycleRunner(
            work_dir=work_dir,
            global_config=global_config or DEFAULT_GLOBAL_CONFIG,
            input_config=input_config,
            variables=variables,
        )

    return _build


@pytest.fixture()
def cleanup_guard(work_dir: Path):
    """Ensure ``destroy --auto-approve`` runs after the test, even on failure.

    Yields a ``ZTFLifecycleRunner`` reference list.  The test appends runners
    it wants cleaned up.  On teardown, each runner's ``destroy()`` is called.

    Usage::

        def test_something(cleanup_guard, lifecycle_runner):
            runner = lifecycle_runner(cfg)
            cleanup_guard.append(runner)
            runner.init()
            runner.apply()
            # ...  (destroy runs automatically on teardown)
    """
    runners: list[ZTFLifecycleRunner] = []
    yield runners
    for runner in reversed(runners):
        try:
            logger.info("Cleanup: destroying resources in %s", runner.work_dir)
            result = runner.destroy(timeout=300)
            if not result.ok:
                logger.warning(
                    "Cleanup destroy failed (exit %d): %s",
                    result.exit_code,
                    result.stderr[:300],
                )
        except Exception as exc:
            logger.error("Cleanup destroy raised: %s", exc)


# ------------------------------------------------------------------
# Pytest configuration
# ------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "functional: functional lifecycle tests")
    config.addinivalue_line("markers", "slow: tests that hit a real PC")
    config.addinivalue_line(
        "markers",
        "namespace(name): filter by Nutanix namespace (e.g. clustermgmt)",
    )
    config.addinivalue_line("markers", "security: security scanning tests")
