"""Security scanner for credential and IP leak detection.

Scans files for:
* Hardcoded passwords and credential patterns
* Private IP address leaks in unexpected locations
* API tokens / bearer tokens
* .gitignore coverage of sensitive files

Returns structured findings with severity levels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    """Finding severity level."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Finding:
    """A single security scan finding."""

    severity: Severity
    category: str
    file: str
    line: int
    message: str
    snippet: str = ""


@dataclass
class ScanReport:
    """Aggregated results of a security scan."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        """Number of CRITICAL findings."""
        return sum(1 for f in self.findings if f.severity is Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        """Number of WARNING findings."""
        return sum(1 for f in self.findings if f.severity is Severity.WARNING)

    @property
    def has_critical(self) -> bool:
        """True when at least one CRITICAL finding exists."""
        return self.critical_count > 0

    def summary(self) -> str:
        """Return a one-line summary of findings."""
        total = len(self.findings)
        return (
            f"{total} finding(s): "
            f"{self.critical_count} critical, "
            f"{self.warning_count} warning, "
            f"{total - self.critical_count - self.warning_count} info"
        )


# ------------------------------------------------------------------
# Patterns
# ------------------------------------------------------------------

_PRIVATE_IP_RE = re.compile(
    r"\b("
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r")\b"
)

_PASSWORD_KEY_RE = re.compile(
    r"(?:password|passwd|secret|api_key|apikey|token|bearer)"
    r"\s*[:=]\s*['\"]?([^\s'\"#]+)",
    re.IGNORECASE,
)

_KNOWN_PASSWORDS = {
    "Nutanix.123",
    "Nutanix/4u",
    "nutanix/4u",
    "Nutanix.1",
}

_BEARER_RE = re.compile(r"(?:Bearer|Basic)\s+[A-Za-z0-9+/=]{20,}", re.IGNORECASE)

_BASE64_SECRET_RE = re.compile(
    r"(?:password|secret|key)\s*[:=]\s*['\"]?"
    r"([A-Za-z0-9+/]{30,}={0,2})['\"]?",
    re.IGNORECASE,
)

_SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".whl",
    ".egg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
}

_SENSITIVE_GITIGNORE_ENTRIES = [
    "env.json",
    ".env",
    "ztfvars.yml",
    "*.auto.ztfvars.yml",
    "state.yml",
]


# ------------------------------------------------------------------
# Scanner
# ------------------------------------------------------------------


def scan_file_for_credentials(
    path: Path,
    known_passwords: set[str] | None = None,
) -> list[Finding]:
    """Scan a single file for credential leaks.

    Args:
        path: File to scan.
        known_passwords: Set of password strings to flag.

    Returns:
        List of findings.
    """
    if path.suffix in _SKIP_EXTENSIONS:
        return []
    passwords = known_passwords or _KNOWN_PASSWORDS
    findings: list[Finding] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []

    rel = str(path)
    in_docstring = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if '"""' in stripped or "'''" in stripped:
            count = stripped.count('"""') + stripped.count("'''")
            if count == 1:
                in_docstring = not in_docstring
            continue
        if in_docstring:
            continue

        for pw in passwords:
            if pw in line:
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category="hardcoded_password",
                        file=rel,
                        line=lineno,
                        message=f"Known password found: {pw[:4]}****",
                        snippet=line.strip()[:120],
                    )
                )

        m = _PASSWORD_KEY_RE.search(line)
        if m:
            val = m.group(1)
            if (
                val
                and val
                not in {
                    "***",
                    "****",
                    "REDACTED",
                    "null",
                    "None",
                    "${PC_PASSWORD}",
                    "${PASSWORD}",
                    '""',
                    "''",
                }
                and not val.startswith("{")
                and not val.startswith("$")
            ):
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        category="credential_pattern",
                        file=rel,
                        line=lineno,
                        message="Password/secret key with inline value",
                        snippet=line.strip()[:120],
                    )
                )

        if _BEARER_RE.search(line):
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    category="bearer_token",
                    file=rel,
                    line=lineno,
                    message="Bearer/Basic auth token detected",
                    snippet=line.strip()[:80],
                )
            )

        if _BASE64_SECRET_RE.search(line):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="base64_secret",
                    file=rel,
                    line=lineno,
                    message="Base64-encoded secret value",
                    snippet=line.strip()[:80],
                )
            )

    return findings


def scan_file_for_ip_leaks(
    path: Path,
    *,
    allowed_ips: set[str] | None = None,
) -> list[Finding]:
    """Scan a file for private IP address leaks.

    Args:
        path: File to scan.
        allowed_ips: IPs that are acceptable (e.g. test fixtures).

    Returns:
        List of findings.
    """
    if path.suffix in _SKIP_EXTENSIONS:
        return []
    allowed = allowed_ips or set()
    findings: list[Finding] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []

    rel = str(path)
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for m in _PRIVATE_IP_RE.finditer(line):
            ip = m.group(1)
            if ip not in allowed:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        category="ip_leak",
                        file=rel,
                        line=lineno,
                        message=f"Private IP address: {ip}",
                        snippet=stripped[:120],
                    )
                )

    return findings


def scan_directory(
    directory: Path,
    *,
    glob_pattern: str = "**/*",
    check_credentials: bool = True,
    check_ips: bool = True,
    known_passwords: set[str] | None = None,
    allowed_ips: set[str] | None = None,
) -> ScanReport:
    """Recursively scan a directory for security issues.

    Args:
        directory: Root directory to scan.
        glob_pattern: File glob pattern.
        check_credentials: Whether to check for credential leaks.
        check_ips: Whether to check for IP leaks.
        known_passwords: Known passwords to flag.
        allowed_ips: IPs that are acceptable.

    Returns:
        Aggregated ``ScanReport``.
    """
    report = ScanReport()
    for path in sorted(directory.glob(glob_pattern)):
        if not path.is_file():
            continue
        if check_credentials:
            report.findings.extend(scan_file_for_credentials(path, known_passwords))
        if check_ips:
            report.findings.extend(
                scan_file_for_ip_leaks(path, allowed_ips=allowed_ips)
            )
    return report


def check_gitignore_coverage(
    repo_root: Path,
    required_entries: list[str] | None = None,
) -> list[Finding]:
    """Verify that .gitignore covers sensitive files.

    Args:
        repo_root: Path to the repository root.
        required_entries: Entries that must appear in .gitignore.

    Returns:
        List of findings for missing entries.
    """
    entries = required_entries or _SENSITIVE_GITIGNORE_ENTRIES
    gitignore_path = repo_root / ".gitignore"
    findings: list[Finding] = []

    if not gitignore_path.exists():
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                category="gitignore_missing",
                file=str(gitignore_path),
                line=0,
                message=".gitignore file does not exist",
            )
        )
        return findings

    content = gitignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines()}

    for entry in entries:
        if entry not in lines:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="gitignore_gap",
                    file=str(gitignore_path),
                    line=0,
                    message=f"Sensitive file pattern '{entry}' not in .gitignore",
                )
            )

    return findings


def scan_log_file(
    log_path: Path,
    known_passwords: set[str] | None = None,
) -> list[Finding]:
    """Scan a ZTF log file for leaked credentials.

    Args:
        log_path: Path to ztf.log.
        known_passwords: Known passwords to flag.

    Returns:
        List of findings.
    """
    if not log_path.exists():
        return []
    passwords = known_passwords or _KNOWN_PASSWORDS
    findings: list[Finding] = []

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel = str(log_path)
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pw in passwords:
            if pw in line:
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category="log_credential_leak",
                        file=rel,
                        line=lineno,
                        message=f"Password leaked in log: {pw[:4]}****",
                        snippet=line.strip()[:120],
                    )
                )

    return findings
