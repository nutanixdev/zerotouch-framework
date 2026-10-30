"""ZTF Lifecycle Runner -- drives init/plan/apply/refresh/import/destroy via subprocess.

Provides a ``ZTFLifecycleRunner`` that:
* writes config files to an isolated working directory,
* invokes ``python -m ztf.main <command>`` as a subprocess,
* captures stdout/stderr/exit-code and returns structured results,
* reads back ``state.yml`` after each step for assertions.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PYTHON = sys.executable


@dataclass
class CommandResult:
    """Structured result of a single ZTF CLI invocation."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True when the command exited cleanly."""
        return self.exit_code == 0


class ZTFLifecycleRunner:
    """Execute ZTF commands in an isolated temp directory.

    Args:
        work_dir: Path to a temporary working directory.
        global_config: Dict written as ``global.yml``.
        input_config: Dict written as ``input.yml``.
        variables: Optional dict written as ``ztfvars.yml``.
    """

    def __init__(
        self,
        work_dir: Path,
        global_config: dict[str, Any],
        input_config: dict[str, Any],
        variables: dict[str, Any] | None = None,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.global_config = global_config
        self.input_config = input_config
        self.variables = variables or {}
        self._history: list[CommandResult] = []
        self._setup_files()

    @property
    def history(self) -> list[CommandResult]:
        """Return the ordered list of every command result."""
        return list(self._history)

    @property
    def state_path(self) -> Path:
        """Path to the state file inside the working directory."""
        return self.work_dir / "state.yml"

    @property
    def log_path(self) -> Path:
        """Path to the ztf log file inside the working directory."""
        return self.work_dir / "ztf.log"

    def _setup_files(self) -> None:
        """Write global.yml, input.yml, and ztfvars.yml at the working directory root."""
        with open(self.work_dir / "global.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.global_config, fh, sort_keys=False)

        with open(self.work_dir / "input.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.input_config, fh, sort_keys=False)

        if self.variables:
            with open(self.work_dir / "ztfvars.yml", "w", encoding="utf-8") as fh:
                yaml.safe_dump(self.variables, fh, sort_keys=False)

    def _read_state(self) -> dict[str, Any]:
        """Read and return current state.yml, or empty dict if absent."""
        if not self.state_path.exists():
            return {}
        with open(self.state_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _run(
        self,
        args: list[str],
        timeout: int = 600,
    ) -> CommandResult:
        """Run ``python -m ztf.main`` with *args* in the working directory.

        Args:
            args: CLI arguments (e.g. ``["plan", "--no-refresh"]``).
            timeout: Seconds before the subprocess is killed.

        Returns:
            A ``CommandResult`` with captured output and post-command state.
        """
        cmd = [_PYTHON, "-m", "ztf.main"] + args
        label = " ".join(args) or "apply"
        logger.info("Running: ztf %s  (cwd=%s)", label, self.work_dir)

        result = subprocess.run(
            cmd,
            cwd=str(self.work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        cr = CommandResult(
            command=label,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            state=self._read_state(),
        )
        self._history.append(cr)

        if not cr.ok:
            logger.warning(
                "ztf %s failed (exit %d): %s",
                label,
                cr.exit_code,
                (cr.stderr or cr.stdout)[:500],
            )
        return cr

    # ------------------------------------------------------------------
    # Public lifecycle commands
    # ------------------------------------------------------------------

    def init(self, *, force: bool = True) -> CommandResult:
        """Run ``ztf init`` -- create an empty state.yml.

        Args:
            force: Pass ``--force`` to skip interactive backup prompt (default True).
        """
        args = ["init"]
        if force:
            args.append("--force")
        return self._run(args)

    def plan(self, *, no_refresh: bool = True) -> CommandResult:
        """Run ``ztf plan``.

        Args:
            no_refresh: Pass ``--no-refresh`` (default True for speed).
        """
        args = ["plan"]
        if no_refresh:
            args.append("--no-refresh")
        return self._run(args)

    def apply(self, *, timeout: int = 600) -> CommandResult:
        """Run ``ztf apply --auto-approve``."""
        return self._run(["apply", "--auto-approve"], timeout=timeout)

    def refresh(self) -> CommandResult:
        """Run ``ztf refresh``."""
        return self._run(["refresh"])

    def import_resource(self, resource_name: str, domain_name: str) -> CommandResult:
        """Run ``ztf import <resource_name> <domain_name>``.

        Args:
            resource_name: Logical resource name as defined in input.yml.
            domain_name: Domain key in input.yml.
        """
        return self._run(["import", resource_name, domain_name])

    def destroy(self, *, timeout: int = 600) -> CommandResult:
        """Run ``ztf destroy --auto-approve``."""
        return self._run(["destroy", "--auto-approve"], timeout=timeout)

    # ------------------------------------------------------------------
    # Composite lifecycle
    # ------------------------------------------------------------------

    def full_lifecycle(self, *, timeout: int = 600) -> dict[str, CommandResult]:
        """Run the complete ZTF lifecycle and return results per step.

        Sequence:
            init -> plan (expect creates) -> apply -> refresh
            -> plan (expect no changes) -> destroy

        Returns:
            Dict keyed by step name to its ``CommandResult``.

        Raises:
            AssertionError: If any critical step fails.
        """
        results: dict[str, CommandResult] = {}

        r = self.init()
        results["init"] = r
        assert r.ok, f"init failed: {r.stderr}"

        r = self.plan(no_refresh=True)
        results["plan_create"] = r
        assert r.ok, f"plan (pre-apply) failed: {r.stderr}"

        r = self.apply(timeout=timeout)
        results["apply"] = r
        assert r.ok, f"apply failed: {r.stderr}"

        r = self.refresh()
        results["refresh"] = r
        assert r.ok, f"refresh failed: {r.stderr}"

        r = self.plan(no_refresh=True)
        results["plan_idempotent"] = r
        assert r.ok, f"plan (idempotent) failed: {r.stderr}"

        r = self.destroy(timeout=timeout)
        results["destroy"] = r
        assert r.ok, f"destroy failed: {r.stderr}"

        return results

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def get_state_resources(self, domain: str | None = None) -> dict[str, Any]:
        """Return the resources dict from current state.

        Args:
            domain: If given, return only that domain's resources.
                    Otherwise return the full ``domains`` dict.
        """
        state = self._read_state()
        domains = state.get("domains", {})
        if domain is None:
            return domains
        return domains.get(domain, {}).get("resources", {})

    def state_has_resource(self, domain: str, entity: str, resource_name: str) -> bool:
        """Check whether a specific resource exists in state."""
        resources = self.get_state_resources(domain)
        return resource_name in resources.get(entity, {})

    def get_resource_ext_id(
        self, domain: str, entity: str, resource_name: str
    ) -> str | None:
        """Return the ext_id for a resource from state, or None."""
        resources = self.get_state_resources(domain)
        entry = resources.get(entity, {}).get(resource_name, {})
        return entry.get("extId") or entry.get("ext_id")
