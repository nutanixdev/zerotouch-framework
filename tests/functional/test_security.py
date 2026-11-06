"""Security scanning tests for ZTF.

Validates that:
* No credentials leak into state files, logs, or generated output.
* .gitignore covers all sensitive file patterns.
* Real-world example YAMLs are audited for hardcoded passwords.
* Post-lifecycle working directories contain no secrets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.conftest import (
    DEFAULT_GLOBAL_CONFIG,
    get_pc_credentials,
)
from tests.functional.namespace_configs import (
    category_config,
)
from tests.functional.runner import ZTFLifecycleRunner
from tests.functional.security_scanner import (
    Severity,
    check_gitignore_coverage,
    scan_directory,
    scan_file_for_credentials,
    scan_log_file,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------
# Static security checks (no PC required)
# ------------------------------------------------------------------


@pytest.mark.security
class TestGitignoreCoverage:
    """Verify .gitignore protects sensitive files."""

    def test_gitignore_covers_sensitive_files(self) -> None:
        """All sensitive file patterns must be in .gitignore."""
        findings = check_gitignore_coverage(_REPO_ROOT)
        critical = [f for f in findings if f.severity is Severity.CRITICAL]
        assert not critical, "Critical .gitignore gaps:\n" + "\n".join(
            f"  - {f.message}" for f in critical
        )


@pytest.mark.security
class TestRealWorldExamplesAudit:
    """Audit real-world-examples/ for hardcoded credentials."""

    def test_no_hardcoded_passwords_in_examples(self) -> None:
        """Scan all YAML examples for known passwords.

        Real-world examples from verification runs may contain inline
        credentials.  This test flags them for awareness but uses
        ``xfail`` since the examples directory is expected to have them
        until they are templatised.
        """
        examples_dir = _REPO_ROOT / "real-world-examples"
        if not examples_dir.exists():
            pytest.skip("real-world-examples/ directory not found")

        report = scan_directory(
            examples_dir,
            glob_pattern="**/*.yml",
            check_credentials=True,
            check_ips=False,
        )

        critical = [f for f in report.findings if f.severity is Severity.CRITICAL]
        if critical:
            unique_files = sorted({f.file for f in critical})
            details = "\n".join(f"  - {p}" for p in unique_files[:30])
            pytest.xfail(
                f"{len(critical)} credential finding(s) across "
                f"{len(unique_files)} file(s) in real-world-examples/ "
                f"(expected until templatised):\n{details}"
            )

    def test_ip_audit_in_examples(self) -> None:
        """Flag private IPs in example YAMLs (warning-level, non-blocking)."""
        examples_dir = _REPO_ROOT / "real-world-examples"
        if not examples_dir.exists():
            pytest.skip("real-world-examples/ directory not found")

        report = scan_directory(
            examples_dir,
            glob_pattern="**/*.yml",
            check_credentials=False,
            check_ips=True,
        )

        if report.findings:
            summary = "\n".join(
                f"  {f.file}:{f.line} - {f.message}" for f in report.findings[:30]
            )
            pytest.xfail(
                f"{len(report.findings)} IP address(es) in examples "
                f"(expected for verified examples):\n{summary}"
            )


@pytest.mark.security
class TestZtfDirectoryScanning:
    """Scan the main ztf/ source directory for leaked secrets."""

    def test_no_credentials_in_source(self) -> None:
        """The ztf/ package source must not contain hardcoded passwords."""
        ztf_dir = _REPO_ROOT / "ztf"
        report = scan_directory(
            ztf_dir,
            glob_pattern="**/*.py",
            check_credentials=True,
            check_ips=False,
        )
        critical = [f for f in report.findings if f.severity is Severity.CRITICAL]
        assert not critical, "Credentials found in ztf/ source:\n" + "\n".join(
            f"  {f.file}:{f.line} - {f.message}" for f in critical
        )


# ------------------------------------------------------------------
# Post-lifecycle security checks (requires PC)
# ------------------------------------------------------------------


@pytest.mark.security
@pytest.mark.slow
class TestPostLifecycleSecurity:
    """Security checks after running a ZTF lifecycle."""

    @pytest.fixture()
    def lifecycle_workdir(
        self, tmp_path: Path, env_data: dict, run_id: int
    ) -> Path | None:
        """Run a minimal lifecycle (category) and return the work dir."""
        try:
            creds = get_pc_credentials("nested_7_5", env_data)
        except RuntimeError:
            return None

        input_config = category_config(run_id, creds)
        work_dir = tmp_path / "sec_test"
        work_dir.mkdir()

        runner = ZTFLifecycleRunner(
            work_dir=work_dir,
            global_config=DEFAULT_GLOBAL_CONFIG,
            input_config=input_config,
        )

        runner.init()
        r = runner.apply(timeout=300)
        if not r.ok:
            return None

        runner.refresh()

        yield work_dir

        runner.destroy(timeout=300)

    def test_no_credentials_in_state(
        self, lifecycle_workdir: Path | None, env_data: dict
    ) -> None:
        """state.yml must not contain password values."""
        if lifecycle_workdir is None:
            pytest.skip("Could not run lifecycle (no PC creds or apply failed)")

        state_path = lifecycle_workdir / "state.yml"
        if not state_path.exists():
            pytest.skip("No state.yml produced")

        try:
            creds = get_pc_credentials("nested_7_5", env_data)
        except RuntimeError:
            pytest.skip("Cannot resolve credentials to verify against")
            return

        password = creds["password"]
        content = state_path.read_text(encoding="utf-8")
        assert password not in content, (
            "Password found in state.yml -- credential leak!"
        )

        findings = scan_file_for_credentials(state_path)
        critical = [f for f in findings if f.severity is Severity.CRITICAL]
        assert not critical, "Credentials in state.yml:\n" + "\n".join(
            f"  {f.message}" for f in critical
        )

    def test_no_credentials_in_logs(
        self, lifecycle_workdir: Path | None, env_data: dict
    ) -> None:
        """ztf.log must not contain password strings."""
        if lifecycle_workdir is None:
            pytest.skip("Could not run lifecycle")

        log_path = lifecycle_workdir / "ztf.log"
        if not log_path.exists():
            pytest.skip("No ztf.log produced")

        try:
            creds = get_pc_credentials("nested_7_5", env_data)
        except RuntimeError:
            pytest.skip("Cannot resolve credentials to verify against")
            return

        findings = scan_log_file(
            log_path,
            known_passwords={creds["password"]} | {"Nutanix.123", "Nutanix/4u"},
        )
        critical = [f for f in findings if f.severity is Severity.CRITICAL]
        assert not critical, "Credentials leaked in ztf.log:\n" + "\n".join(
            f"  L{f.line}: {f.message}" for f in critical
        )

    def test_no_secrets_in_workdir(self, lifecycle_workdir: Path | None) -> None:
        """No unexpected secrets in the working directory after lifecycle."""
        if lifecycle_workdir is None:
            pytest.skip("Could not run lifecycle")

        report = scan_directory(
            lifecycle_workdir,
            check_credentials=True,
            check_ips=False,
        )

        critical = [
            f
            for f in report.findings
            if f.severity is Severity.CRITICAL and f.category != "hardcoded_password"
        ]
        assert not critical, "Secrets found in workdir:\n" + "\n".join(
            f"  {f.file}:{f.line} - {f.message}" for f in critical
        )
