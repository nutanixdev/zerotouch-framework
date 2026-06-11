"""ZTF CLI entry point.

Orchestrates config loading, provider execution, and state management.
"""

from __future__ import annotations

import glob
import logging
import os
import platform
import shutil
import signal
import stat
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any, BinaryIO, TextIO, TypeVar

if TYPE_CHECKING:
    from ztf.repl import ReplContext

import click
import yaml

from ztf.config.config_loader import load_config, parse_var_string
from ztf.config.functions import resolve_functions_file
from ztf.config.interpolation import classify_unresolved_tokens, has_tokens
from ztf.plan_file import (
    PlanFileError,
    read_plan_file,
    verify_plan_file,
    write_plan_file,
)
from ztf.provider.provider import Provider, _compute_field_diff
from ztf.utils.utils import (
    LocalTimeFormatter,
    file_logger_format,
    get_logger,
    read_input_file,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared Click option decorator
# ---------------------------------------------------------------------------


F = TypeVar("F", bound=Callable[..., object])


def _common_io_options(fn: F) -> F:
    """Attach shared --input/--global-file/--state/--parallel/--var/--var-file/--functions options."""
    for decorator in reversed(
        [
            click.option(
                "--input",
                "-i",
                default="input.yml",
                show_default=True,
                help="Path to entity configuration file",
            ),
            click.option(
                "--global-file",
                "-g",
                default="global.yml",
                show_default=True,
                help="Path to global SDK configuration file",
            ),
            click.option(
                "--state",
                "-s",
                default="state.yml",
                show_default=True,
                help="Path to state file (manages infrastructure state)",
            ),
            click.option(
                "--parallel",
                "-p",
                type=int,
                default=None,
                help="Maximum number of parallel workers",
            ),
            click.option(
                "--var",
                multiple=True,
                metavar="KEY=VALUE",
                help="Variable override: --var 'key=value' (repeatable)",
            ),
            click.option(
                "--var-file",
                multiple=True,
                type=click.Path(),
                help="Path to a YAML variable file (repeatable)",
            ),
            click.option(
                "--functions",
                type=click.Path(),
                default=None,
                help="Path to Python functions file for {fn.*} tokens (auto-discovered if not specified)",
            ),
        ]
    ):
        fn = decorator(fn)
    return fn


def _repl_io_options(fn: F) -> F:
    """Attach REPL-specific options: --input, --global-file, --var, --var-file."""
    for decorator in reversed(
        [
            click.option(
                "--input",
                "-i",
                default="input.yml",
                show_default=True,
                help="Path to entity configuration file",
            ),
            click.option(
                "--global-file",
                "-g",
                default="global.yml",
                show_default=True,
                help="Path to global SDK configuration file",
            ),
            click.option(
                "--var",
                multiple=True,
                metavar="KEY=VALUE",
                help="Variable override: --var 'key=value' (repeatable)",
            ),
            click.option(
                "--var-file",
                multiple=True,
                type=click.Path(),
                help="Path to a YAML variable file (repeatable)",
            ),
        ]
    ):
        fn = decorator(fn)
    return fn


# ---------------------------------------------------------------------------
# Auto-loaded variable files (ztfvars)
# ---------------------------------------------------------------------------


def discover_auto_var_files() -> list[str]:
    """Discover auto-loaded variable files in the working directory.

    Mirrors Terraform's ``terraform.tfvars`` / ``*.auto.tfvars`` convention.
    Files are returned in load order (earlier entries have lower precedence):

    1. ``ztfvars.yml`` -- primary secrets/variables file.
    2. ``*.auto.ztfvars.yml`` -- additional files, sorted alphabetically.

    Returns:
        List of file paths that exist and should be loaded.
    """
    found: list[str] = []
    if os.path.isfile("ztfvars.yml"):
        found.append("ztfvars.yml")
    for path in sorted(glob.glob("*.auto.ztfvars.yml")):
        if os.path.isfile(path):
            found.append(path)
    return found


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def configure_root_logger(debug: bool, log_dir: str | None = None) -> None:
    """Configure root logger for file and stream output.

    The file handler on root always captures DEBUG (including tracebacks
    logged with ``exc_info=True``).  Per-module stream handlers (added by
    ``get_logger``) default to INFO and are promoted to DEBUG only when
    *debug* is True — keeping console output clean by default.

    Args:
        debug: When True, stream handlers are set to DEBUG.
        log_dir: Directory to write ``ztf.log`` into.  Defaults to CWD
            when *None*.  CLI commands pass the input file's parent
            directory so the log lives alongside the config.
    """
    log_path = os.path.join(log_dir, "ztf.log") if log_dir else "ztf.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = []

    file_handler = RotatingFileHandler(
        log_path,
        mode="a",
        encoding="utf-8",
        delay=True,
        maxBytes=1_000 * 1024,
        backupCount=10,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(LocalTimeFormatter(fmt=file_logger_format))
    root.addHandler(file_handler)

    # Adjust per-module stream handlers to match --debug flag
    stream_level = logging.DEBUG if debug else logging.INFO
    for lgr in logging.Logger.manager.loggerDict.values():
        if isinstance(lgr, logging.Logger):
            for handler in lgr.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(
                    handler, logging.FileHandler
                ):
                    handler.setLevel(stream_level)


# ---------------------------------------------------------------------------
# Plan display
# ---------------------------------------------------------------------------


def print_plan(plan_result: dict) -> None:
    """Pretty-print the plan result with field-level diffs for updates."""
    for action, domains in plan_result.items():
        if not domains:
            continue
        action_upper = action.upper()
        for domain, entities in domains.items():
            for entity, resources in entities.items():
                for resource in resources:
                    name = resource.get("resource_name", "?")
                    if action == "operations":
                        op_type = resource.get("type", "?")
                        logger.info(
                            f"  [{action_upper}] {domain} > {entity}/{name}: {op_type}"
                        )
                    else:
                        logger.info(f"  [{action_upper}] {domain} > {entity}/{name}")
                    diff_fields = resource.get("diff_fields")
                    if diff_fields:
                        for field, val in diff_fields.get("added", {}).items():
                            logger.info(f"    + {field}: {val}")
                        for field, val in diff_fields.get("removed", {}).items():
                            logger.info(f"    - {field}: {val}")
                        for field, vals in diff_fields.get("changed", {}).items():
                            logger.info(
                                f"    ~ {field}: {vals['old']} -> {vals['new']}"
                            )


def _count_plan_changes(plan_result: dict) -> tuple[int, int, int, int]:
    """Count total resources per action from a plan result.

    Returns:
        (create, update, delete, operations) counts.
    """
    counts: dict[str, int] = {}
    for action in ("create", "update", "delete", "operations"):
        total = 0
        for entities in plan_result.get(action, {}).values():
            for resources in entities.values():
                total += len(resources)
        counts[action] = total
    return counts["create"], counts["update"], counts["delete"], counts["operations"]


def _print_plan_summary(create: int, update: int, delete: int, operations: int) -> None:
    """Print a Terraform-style summary line for a plan."""
    parts: list[str] = []
    if create:
        parts.append(f"{create} to create")
    if update:
        parts.append(f"{update} to update")
    if delete:
        parts.append(f"{delete} to delete")
    if operations:
        parts.append(f"{operations} operation(s) to run")
    if parts:
        logger.info(f"\nPlan: {', '.join(parts)}.")
    else:
        logger.info("\nNo changes. Infrastructure is up-to-date.")


def _classify_unresolved_plan_resources(
    plan_result: dict,
    config: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Classify plan entries with unresolved tokens.

    Returns:
        ``(known_after_apply, failed)`` where *known_after_apply* lists
        resource names whose only unresolved tokens are resource-to-resource
        references (will resolve during apply), and *failed* lists names
        with data source or other unresolvable tokens.
    """
    all_resource_names: set[str] = set()
    all_domain_names: set[str] = set(config.get("domains", {}).keys())
    for domain_cfg in config.get("domains", {}).values():
        for entity_resources in domain_cfg.get("resources", {}).values():
            all_resource_names.update(entity_resources)

    known_after_apply: list[str] = []
    failed: list[str] = []

    for action in ("create", "update"):
        for domain_name, entities in plan_result.get(action, {}).items():
            for entity, resources in entities.items():
                for entry in resources:
                    payload = {
                        k: v
                        for k, v in entry.items()
                        if k not in ("resource_name", "diff_fields")
                    }
                    if not has_tokens(payload):
                        continue
                    rname = entry.get("resource_name", "unknown")
                    label = f"{domain_name} > {entity}/{rname}"
                    res_refs, fail_refs = classify_unresolved_tokens(
                        payload, all_resource_names, all_domain_names
                    )
                    if fail_refs:
                        failed.append(label)
                    elif res_refs:
                        known_after_apply.append(label)

    return known_after_apply, failed


def _print_unresolved_warnings(
    known_after_apply: list[str],
    failed: list[str],
) -> None:
    """Log categorised warnings for unresolved interpolation tokens.

    Args:
        known_after_apply: Resource labels with resource-to-resource refs
            that will resolve at apply time.
        failed: Resource labels with data-source or other unresolvable refs.
    """
    if known_after_apply:
        names = ", ".join(known_after_apply)
        logger.info(
            "\nNote: %d resource(s) have values known after apply: %s",
            len(known_after_apply),
            names,
        )
    if failed:
        names = ", ".join(failed)
        logger.warning(
            "\nWarning: %d resource(s) contain unresolved interpolation "
            "tokens (failed data sources or missing variables). "
            "Apply will fail for these resources: %s",
            len(failed),
            names,
        )


def _print_refresh_diff(
    previous: dict[str, object], refreshed: dict[str, object]
) -> None:
    """Log what changed during a state refresh with field-level diffs.

    Args:
        previous: State dict before refresh.
        refreshed: State dict after refresh.
    """
    prev_domains = previous.get("domains", {})
    ref_domains = refreshed.get("domains", {})
    changed = 0
    removed = 0
    unchanged = 0

    if not isinstance(prev_domains, dict):
        prev_domains = {}
    if not isinstance(ref_domains, dict):
        ref_domains = {}

    for domain_name, prev_domain in prev_domains.items():
        if not isinstance(prev_domain, dict):
            continue
        ref_domain = ref_domains.get(domain_name, {})
        if not isinstance(ref_domain, dict):
            ref_domain = {}
        prev_resources = prev_domain.get("resources", {})
        ref_resources = ref_domain.get("resources", {})
        if not isinstance(prev_resources, dict):
            prev_resources = {}
        if not isinstance(ref_resources, dict):
            ref_resources = {}

        for entity, prev_entity_resources in prev_resources.items():
            if not isinstance(prev_entity_resources, dict):
                continue
            ref_entity_resources = ref_resources.get(entity, {})
            if not isinstance(ref_entity_resources, dict):
                ref_entity_resources = {}

            for rname in prev_entity_resources:
                if rname not in ref_entity_resources:
                    logger.info("  [REMOVED] %s > %s/%s", domain_name, entity, rname)
                    removed += 1
                else:
                    prev_body = prev_entity_resources[rname].get("body", {})
                    ref_body = ref_entity_resources[rname].get("body", {})
                    if prev_body != ref_body:
                        logger.info(
                            "  [CHANGED] %s > %s/%s", domain_name, entity, rname
                        )
                        diff = _compute_field_diff(
                            prev_body if isinstance(prev_body, dict) else {},
                            ref_body if isinstance(ref_body, dict) else {},
                        )
                        for field, val in diff.get("added", {}).items():
                            logger.info("    + %s: %s", field, val)
                        for field, val in diff.get("removed", {}).items():
                            logger.info("    - %s: %s", field, val)
                        for field, vals in diff.get("changed", {}).items():
                            logger.info(
                                "    ~ %s: %s -> %s", field, vals["old"], vals["new"]
                            )
                        changed += 1
                    else:
                        unchanged += 1

    total = changed + removed + unchanged
    if total:
        logger.info(
            "\nRefreshed %d resource(s): %d changed, %d removed, %d unchanged.",
            total,
            changed,
            removed,
            unchanged,
        )
    else:
        logger.info("\nNo resources to refresh.")


def _merge_non_targeted_state(
    new_state: dict[str, Any],
    full_prev_map: dict[str, dict[str, dict[str, dict[str, Any]]]],
    targeted_map: dict[str, dict[str, dict[str, dict[str, Any]]]],
    previous_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge non-targeted resources back into the state after targeted destroy.

    Resources that were not included in *targeted_map* are carried over
    from *full_prev_map* so they are not lost from state.

    Args:
        new_state: State returned by ``provider.destroy()``.
        full_prev_map: The complete previous entity resource map.
        targeted_map: The filtered map of only targeted resources.
        previous_state: Raw previous state dict for host lookup.

    Returns:
        State dict with non-targeted resources preserved.
    """
    prev_domains = (previous_state or {}).get("domains", {})
    for dn, entities in full_prev_map.items():
        for ent, resources in entities.items():
            for rname, rdata in resources.items():
                targeted_in_domain = targeted_map.get(dn, {}).get(ent, {})
                if rname in targeted_in_domain:
                    continue
                host = prev_domains.get(dn, {}).get("host", dn)
                domain_state = new_state.setdefault("domains", {}).setdefault(
                    dn, {"host": host, "resources": {}}
                )
                domain_state.setdefault("resources", {}).setdefault(ent, {})[rname] = (
                    rdata
                )
    return new_state


def _print_destroy_plan(
    resource_map: dict[str, dict[str, dict[str, Any]]],
) -> int:
    """Log each resource that will be destroyed and return the total count.

    Args:
        resource_map: ``{domain: {entity: {resource_name: data}}}``.

    Returns:
        Total number of resources to destroy.
    """
    total = 0
    for domain_name, entities in resource_map.items():
        for entity, resources in entities.items():
            for resource_name in resources:
                logger.info(
                    "  [DESTROY] %s > %s/%s", domain_name, entity, resource_name
                )
                total += 1
    return total


def _print_run_summary(run_results: dict[str, list], label: str = "Apply") -> None:
    """Print a post-run summary from in-memory run results.

    Args:
        run_results: Dict mapping domain name to list of operation result
            dicts produced by ``Provider.run()`` or ``Provider.destroy()``.
        label: Action label for the summary line (e.g. ``"Apply"``,
            ``"Destroy"``).
    """
    if not run_results:
        logger.info("\n%s complete! Resources: 0 changes.", label)
        return

    counts: dict[str, int] = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    errors = 0
    for results in run_results.values():
        for entry in results:
            op = entry.get("operation", "")
            if entry.get("error"):
                errors += 1
            elif op in counts:
                counts[op] += 1

    parts = []
    if counts["create"]:
        parts.append(f"{counts['create']} created")
    if counts["update"]:
        parts.append(f"{counts['update']} updated")
    if counts["delete"]:
        parts.append(f"{counts['delete']} deleted")
    if counts["replace"]:
        parts.append(f"{counts['replace']} replaced")

    summary = ", ".join(parts) if parts else "0 changes"
    logger.info("\n%s complete! Resources: %s.", label, summary)
    if errors:
        logger.info(
            "%d resource(s) had errors. Check ztf.log in the config directory for details.",
            errors,
        )


def _confirm_action(action_label: str) -> bool:
    """Prompt the user for explicit 'yes' confirmation.

    Args:
        action_label: Human-readable label (e.g. "apply", "destroy").

    Returns:
        True if the user typed 'yes', False otherwise.
    """
    try:
        click.echo(
            f"\nDo you want to perform these actions?\n"
            f"  ZTF will perform the actions described above.\n"
            f"  Only 'yes' will be accepted to {action_label}.\n"
        )
        answer = click.prompt("  Enter a value", default="", show_default=False)
    except (click.exceptions.Abort, EOFError, KeyboardInterrupt):
        click.echo()
        return False
    return answer.strip().lower() == "yes"


# ---------------------------------------------------------------------------
# Import helper
# ---------------------------------------------------------------------------


def _import_single_resource(
    resource_name: str,
    domain_name: str,
    provider: Provider,
    config: dict[str, Any],
    previous_state: dict[str, Any],
    state_path: str,
) -> None:
    """Import one resource using an already-initialised provider.

    This is the inner workhorse called by both single and bulk import
    paths so that config loading / SDK initialisation / data-source
    fetching happen only once.
    """
    import_result = provider.import_resource_data(resource_name, domain_name)

    if import_result is None:
        raise ValueError(f"Failed to import resource '{resource_name}'")

    entity_name = import_result["entity_name"]
    sanitized_data = import_result["sanitized_data"]
    ext_id = import_result["extId"]

    sanitized_data.pop("extId", None)
    sanitized_data.pop("ext_id", None)

    state_domains = previous_state.get("domains", {})
    host = config.get("domains", {}).get(domain_name, {}).get("host", domain_name)
    if domain_name not in state_domains:
        state_domains[domain_name] = {"host": host, "resources": {}}
    domain_state = state_domains[domain_name]
    domain_state.setdefault("resources", {}).setdefault(entity_name, {})
    resource_entry = import_result["resource_entry"]
    state_entry: dict[str, object] = {"extId": ext_id, "body": sanitized_data}
    rules = resource_entry.get("rules")
    if rules:
        state_entry["rules"] = rules
    domain_state["resources"][entity_name][resource_name] = state_entry

    previous_state["domains"] = state_domains
    _write_state(state_path, previous_state)
    logger.info(
        "Imported resource '%s' into state. "
        "Ensure the matching config exists in your input file.",
        resource_name,
    )

    suggested: dict[str, object] = {"extId": ext_id, "body": sanitized_data}
    snippet = yaml.safe_dump(
        {resource_name: suggested}, default_flow_style=False, sort_keys=False
    )
    logger.info(
        "\nSuggested config for your input file "
        "(under domains > %s > resources > %s):\n\n%s",
        domain_name,
        entity_name,
        snippet,
    )


def _attach_run_results_path(provider: Provider, state_path: str) -> None:
    """Point the provider's audit JSON at the state-file directory.

    ``ztf_run_results.json`` historically lived in the cwd, which meant
    running ``ztf apply`` from anywhere but the config directory scattered
    audit files across the filesystem.  Colocating it with the state
    file matches the log-file placement and keeps artifacts together.
    """
    provider.run_results_path = (
        Path(state_path).resolve().parent / "ztf_run_results.json"
    )


def _build_import_provider(
    global_file: str,
    input_file: str,
    state: str,
    var: tuple[str, ...],
    var_file: tuple[str, ...],
    functions_file: str | None = None,
) -> tuple[Provider, dict[str, Any], dict[str, Any]]:
    """Create a shared Provider + config + state for import operations.

    Mirrors the setup in ``plan``/``apply``: auto-discovers ``ztfvars.yml``,
    loads functions, and configures logging.

    Returns:
        ``(provider, config, previous_state)``
    """
    global_config_data = _load_config_file(global_file)
    input_config_data = _load_config_file(input_file)
    configure_root_logger(
        global_config_data.get("config", {}).get("debug", False),
        log_dir=os.path.dirname(os.path.abspath(input_file)),
    )

    var_overrides = _parse_vars(var)
    all_var_files = _collect_var_files(var_file)
    fn_map = resolve_functions_file(functions_file, input_file)
    config = load_config(
        input_config_data,
        var_overrides=var_overrides or None,
        var_files=all_var_files or None,
        functions=fn_map,
    )

    if os.path.exists(state):
        with open(state, encoding="utf-8") as fh:
            raw_state = yaml.safe_load(fh) or {}
    else:
        raise FileNotFoundError(
            f"State file '{state}' not found. Run 'ztf init' first."
        )

    provider = Provider(global_config_data, config, raw_state)
    _attach_run_results_path(provider, state)
    return provider, config, raw_state


# ---------------------------------------------------------------------------
# State file helpers
# ---------------------------------------------------------------------------


_IS_WINDOWS = platform.system() == "Windows"


class _BaseStateFileLock:
    """Cross-platform skeleton for an advisory state-file lock.

    **Do not use directly.**  All state-file I/O must go through
    ``_read_state()`` and ``_write_state()``, which acquire the lock
    internally.  Bypassing those helpers risks silent data corruption
    or ``PermissionError`` on Windows.

    Subclasses implement four hooks that differ by platform:

    * :meth:`_open_handle` — open and return the file-object that will
      hold the lock.
    * :meth:`_acquire` / :meth:`_release` — the OS-specific lock calls.
    * :meth:`_cleanup` — post-``__exit__`` housekeeping (Windows deletes
      a sentinel file; Unix is a no-op).
    """

    # msvcrt.locking requires a byte count > 0.  4 bytes is the smallest
    # power-of-two that satisfies alignment expectations on all Windows
    # versions and is large enough to be visible in a hex dump during
    # debugging.  The sentinel file contains only these null bytes and
    # is never interpreted as data.
    _LOCK_SIZE = 4

    def __init__(self, path: str) -> None:
        self.path = path
        self.file: BinaryIO | TextIO | None = None

    def __enter__(self) -> BinaryIO | TextIO:
        self.file = self._open_handle()
        if self.file is None:
            raise RuntimeError(f"Failed to open state file {self.path}")
        self._acquire()
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self._release()
            self.file.close()
            self._cleanup()

    def _require_file(self) -> BinaryIO | TextIO:
        """Return the open handle, narrowing its type for subclasses.

        The base ``__enter__`` guarantees ``self.file`` is non-None
        before ``_acquire``/``_release`` are called, but the type
        checker cannot prove that across method boundaries.  A single
        guard here keeps hook bodies free of boilerplate.
        """
        if self.file is None:
            raise RuntimeError(f"Lock file handle for {self.path!r} is not open")
        return self.file

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    def _open_handle(self) -> BinaryIO | TextIO:
        raise NotImplementedError

    def _acquire(self) -> None:
        raise NotImplementedError

    def _release(self) -> None:
        raise NotImplementedError

    def _cleanup(self) -> None:  # pragma: no cover - default no-op
        pass


class _UnixStateFileLock(_BaseStateFileLock):
    """``fcntl.flock``-based advisory lock on the state file itself."""

    def _open_handle(self) -> BinaryIO | TextIO:
        # The returned handle is owned by ``_BaseStateFileLock.__exit__``,
        # which closes it after releasing the advisory lock; a ``with``
        # statement here would close the fd before the lock is acquired.
        try:
            # Open append+read so the file is created if absent, but we
            # never truncate existing content — the lock is advisory only.
            return open(self.path, "a+", encoding="utf-8")  # noqa: SIM115
        except PermissionError:
            # State file was set read-only by a previous ``_write_state``
            # call.  fcntl advisory locks don't require write permission
            # so a read-only handle is sufficient.
            return open(self.path, encoding="utf-8")  # noqa: SIM115

    def _acquire(self) -> None:
        import fcntl

        fcntl.flock(self._require_file(), fcntl.LOCK_EX)

    def _release(self) -> None:
        import fcntl

        fcntl.flock(self._require_file(), fcntl.LOCK_UN)


class _WindowsStateFileLock(_BaseStateFileLock):
    """``msvcrt.locking``-based lock held on a ``<path>.lock`` sentinel.

    Windows mandatory byte-range locks block every handle against the
    target file — including handles in the *same* process — so the lock
    is held on a dedicated sentinel file rather than the state file.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._lock_path = path + ".lock"

    def _open_handle(self) -> BinaryIO | TextIO:
        # Handle ownership is transferred to ``_BaseStateFileLock.__exit__``
        # (same as the Unix backend); see note there.
        fh = open(self._lock_path, "wb")  # noqa: SIM115
        fh.write(b"\x00" * self._LOCK_SIZE)
        fh.flush()
        fh.seek(0)
        return fh

    def _acquire(self) -> None:
        import msvcrt

        fh = self._require_file()
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, self._LOCK_SIZE)  # type: ignore[attr-defined]

    def _release(self) -> None:
        import msvcrt

        fh = self._require_file()
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, self._LOCK_SIZE)  # type: ignore[attr-defined]
        except OSError:
            # Already-unlocked or transient; the handle is about to
            # close anyway, so this is safe to swallow.
            pass

    def _cleanup(self) -> None:
        try:
            os.remove(self._lock_path)
        except OSError as exc:
            # Non-fatal: another process may still hold the file open.
            # The sentinel is overwritten on the next lock attempt, so
            # stale files do not block future operations.
            logger.debug("Could not remove lock file %s: %s", self._lock_path, exc)


#: Platform-appropriate state-file lock.  All call sites construct
#: ``_StateFileLock(path)`` and receive the correct backend.
_StateFileLock: type[_BaseStateFileLock] = (
    _WindowsStateFileLock if _IS_WINDOWS else _UnixStateFileLock
)


def _set_readonly(path: str) -> None:
    """Mark a file as read-only (cross-platform)."""
    if _IS_WINDOWS:
        os.chmod(path, stat.S_IREAD)
    else:
        os.chmod(path, 0o444)


def _set_writable(path: str) -> None:
    """Mark a file as writable (cross-platform)."""
    if _IS_WINDOWS:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    else:
        os.chmod(path, 0o644)


def _validate_file_path(path: str, label: str) -> None:
    """Ensure *path* exists and is a regular file.

    Args:
        path: Filesystem path to validate.
        label: Human-readable label for error messages (e.g. "State file").

    Raises:
        FileNotFoundError: If the path does not exist.
        IsADirectoryError: If the path is a directory.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} '{path}' not found.")
    if os.path.isdir(path):
        raise IsADirectoryError(f"{label} '{path}' is a directory, not a file.")


def _read_state(state_path: str) -> dict:
    """Read and return the state dict from *state_path* (locked).

    Always use this function — never open the state file directly.

    Raises:
        FileNotFoundError: If the state file does not exist.
        IsADirectoryError: If the path is a directory instead of a file.
    """
    _validate_file_path(state_path, "State file")
    with _StateFileLock(state_path), open(state_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _write_state(state_path: str, state_data: dict) -> None:
    """Write state to disk (locked, then set read-only).

    Creates a ``.bak`` backup of the existing state file before writing.
    Always use this function — never open the state file directly.
    """
    if os.path.exists(state_path):
        backup_path = state_path + ".bak"
        _set_writable(state_path)
        if os.path.exists(backup_path):
            _set_writable(backup_path)
        shutil.copy2(state_path, backup_path)
    with _StateFileLock(state_path), open(state_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(state_data, fh, sort_keys=False)
    _set_readonly(state_path)


def _write_outputs(output_path: str, outputs: dict) -> None:
    """Write resolved outputs to a file (YAML or JSON)."""
    from ztf.utils.utils import write_output_file

    write_output_file(output_path, outputs)
    logger.info(f"Outputs written to {output_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _load_config_file(path: str) -> dict:
    """Read a config YAML file with user-friendly errors.

    Args:
        path: Path to the YAML config file.

    Returns:
        Parsed YAML as a dict.

    Raises:
        click.ClickException: When the file is missing, is a directory, or is empty.
    """
    try:
        _validate_file_path(path, "Config file")
        if os.path.getsize(path) == 0:
            raise click.ClickException(f"Config file '{path}' is empty.")
        data = read_input_file(path)
        if data is None or (isinstance(data, dict) and not data):
            raise click.ClickException(f"Config file '{path}' is empty.")
        return data
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc


def _build_repl_context(
    global_file: str,
    input_file: str,
    var_overrides: dict[str, str] | None,
    var_files: list[str] | None,
) -> ReplContext:
    """Load config and build REPL context.

    Args:
        global_file: Path to global.yml.
        input_file: Path to input.yml.
        var_overrides: Variable overrides from --var.
        var_files: Variable file paths from --var-file and auto ztfvars.

    Returns:
        ReplContext with handlers and data namespace.

    Raises:
        click.ClickException: On missing config file.
        ValueError: On invalid config.
    """
    from ztf.repl import build_repl_context

    global_config_data = _load_config_file(global_file)
    input_config_data = _load_config_file(input_file)
    config = load_config(
        input_config_data,
        var_overrides=var_overrides or None,
        var_files=var_files or None,
    )
    return build_repl_context(global_config_data, config)


def _start_repl(
    locals_dict: dict[str, object],
    exec_code: str | None = None,
    script_path: str | None = None,
) -> None:
    """Start the REPL with the given locals and optional exec/script.

    Args:
        locals_dict: Dict with ctx and data (from ReplContext.to_locals()).
        exec_code: Code to execute (from --exec).
        script_path: Path to script to run (from --script).
    """
    from ztf.repl import start_repl

    start_repl(locals_dict=locals_dict, exec_code=exec_code, script_path=script_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="nutanix-ztf")
def cli() -> None:
    """ZTF — Zero Touch Framework for Nutanix Prism Central IaC."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--state",
    "-s",
    default="state.yml",
    show_default=True,
    help="Path to state file (parent directories are created if missing)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing state file without prompting (backs it up first).",
)
def init(state: str, force: bool) -> None:
    """Create an empty state file."""
    parent = os.path.dirname(state)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(state):
        if not force:
            answer = click.prompt(
                f"State file '{state}' already exists. Overwrite? [y/N]",
                default="N",
                show_default=False,
            )
            if answer.strip().lower() not in ("y", "yes"):
                click.echo("Aborted. Existing state preserved.")
                return
        logger.info("Backed up existing state to '%s'.", state + ".bak")
    _write_state(state, {"domains": {}})
    logger.info("State file '%s' initialised and set to read-only.", state)


# ---------------------------------------------------------------------------
# examples
# ---------------------------------------------------------------------------


@cli.command(name="examples")
@click.option(
    "--namespace",
    default=None,
    help="Generate examples for a single namespace only (default: all)",
)
@click.option(
    "--output-dir",
    default=None,
    type=click.Path(),
    help="Output directory (default: ./examples/ in current working directory)",
)
def generate_examples(namespace: str | None, output_dir: str | None) -> None:
    """Generate per-entity YAML examples and Markdown reference docs."""
    from ztf.generate_examples import generate_all

    generate_all(
        namespace_filter=namespace,
        output_dir=Path(output_dir) if output_dir else None,
    )


# ---------------------------------------------------------------------------
# repl
# ---------------------------------------------------------------------------


@cli.command()
@_repl_io_options
@click.option(
    "--exec",
    "exec_code",
    default=None,
    metavar="CODE",
    help="Execute one-line code and exit (mutually exclusive with --script)",
)
@click.option(
    "--script",
    "script_path",
    default=None,
    type=click.Path(exists=True),
    metavar="PATH",
    help="Run a Python script and exit (mutually exclusive with --exec)",
)
def repl(
    input: str,  # noqa: A002
    global_file: str,
    var: tuple[str, ...],
    var_file: tuple[str, ...],
    exec_code: str | None,
    script_path: str | None,
) -> None:
    """Start an interactive REPL or run code/script with ctx and data namespace."""
    if exec_code is not None and script_path is not None:
        raise click.UsageError("--exec and --script are mutually exclusive.")
    try:
        configure_root_logger(
            _load_config_file(global_file).get("config", {}).get("debug", False),
            log_dir=os.path.dirname(os.path.abspath(input)),
        )
        var_overrides = _parse_vars(var)
        all_var_files = _collect_var_files(var_file)
        ctx = _build_repl_context(
            global_file=global_file,
            input_file=input,
            var_overrides=var_overrides or None,
            var_files=all_var_files or None,
        )
        _start_repl(
            locals_dict=ctx.to_locals(),
            exec_code=exec_code,
            script_path=script_path,
        )
    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


@cli.command()
@_common_io_options
def refresh(
    input: str,  # noqa: A002
    global_file: str,
    state: str,
    parallel: int | None,
    var: tuple,
    var_file: tuple,
    functions: str | None,
) -> None:
    """Sync state from live infrastructure."""
    try:
        global_config_data = _load_config_file(global_file)
        input_config_data = _load_config_file(input)
        configure_root_logger(
            global_config_data.get("config", {}).get("debug", False),
            log_dir=os.path.dirname(os.path.abspath(input)),
        )

        var_overrides = _parse_vars(var)
        all_var_files = _collect_var_files(var_file)
        fn_map = resolve_functions_file(functions, input)
        config = load_config(
            input_config_data,
            var_overrides=var_overrides or None,
            var_files=all_var_files or None,
            functions=fn_map,
        )
        raw_state = _read_state(state)
        previous_state = raw_state
        provider = Provider(global_config_data, config, previous_state)
        _attach_run_results_path(provider, state)
        if parallel is not None:
            provider.max_workers = parallel

        try:
            refreshed_state = provider.refresh_state()
        except Exception as exc:
            logger.error("Failed to refresh state: %s", exc)
            raise SystemExit(1) from exc

        _print_refresh_diff(previous_state, refreshed_state)
        _write_state(state, refreshed_state)
        logger.info("State file refreshed and set to read-only.")

    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


@cli.command()
@_common_io_options
@click.option(
    "--no-refresh",
    is_flag=True,
    default=False,
    help="Skip automatic state refresh before plan",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Fail on refresh errors instead of proceeding with stale state",
)
@click.option(
    "--out",
    "out",
    default=None,
    type=click.Path(),
    help=(
        "Write the plan to FILE for use with 'ztf apply --plan FILE'. "
        "The file pins the input + state hashes so apply can detect drift."
    ),
)
def plan(
    input: str,  # noqa: A002
    global_file: str,
    state: str,
    parallel: int | None,
    var: tuple,
    var_file: tuple,
    functions: str | None,
    no_refresh: bool,
    strict: bool,
    out: str | None,
) -> None:
    """Preview what will change (auto-refreshes state first)."""
    try:
        global_config_data = _load_config_file(global_file)
        input_config_data = _load_config_file(input)
        configure_root_logger(
            global_config_data.get("config", {}).get("debug", False),
            log_dir=os.path.dirname(os.path.abspath(input)),
        )

        var_overrides = _parse_vars(var)
        all_var_files = _collect_var_files(var_file)
        fn_map = resolve_functions_file(functions, input)
        config = load_config(
            input_config_data,
            var_overrides=var_overrides or None,
            var_files=all_var_files or None,
            functions=fn_map,
        )
        raw_state = _read_state(state)
        previous_state = raw_state
        provider = Provider(global_config_data, config, previous_state)
        _attach_run_results_path(provider, state)
        if parallel is not None:
            provider.max_workers = parallel

        effective_state = previous_state
        if not no_refresh and previous_state.get("domains"):
            try:
                logger.info("Refreshing state before plan...")
                refreshed_state = provider.refresh_state()
                _write_state(state, refreshed_state)
                provider = Provider(global_config_data, config, refreshed_state)
                _attach_run_results_path(provider, state)
                if parallel is not None:
                    provider.max_workers = parallel
                effective_state = refreshed_state
            except Exception as exc:
                if strict:
                    logger.error("Refresh failed and --strict is set: %s", exc)
                    raise SystemExit(1) from exc
                logger.warning(
                    "Failed to refresh state before plan: %s. Using stale state.", exc
                )

        plan_result = provider.plan()
        print_plan(plan_result)
        create, update, delete, operations = _count_plan_changes(plan_result)
        _print_plan_summary(create, update, delete, operations)

        known_after_apply, failed = _classify_unresolved_plan_resources(
            plan_result, config
        )
        _print_unresolved_warnings(known_after_apply, failed)

        if out is not None:
            saved = write_plan_file(
                out,
                operations=plan_result,
                input_config=config,
                state_data=effective_state,
            )
            click.echo(
                f"Plan written to {out} "
                f"(input_hash={saved.input_hash[:12]}..., "
                f"state_hash={saved.state_hash[:12]}...)."
            )

    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


@cli.command()
@_common_io_options
@click.option(
    "--output-file",
    default=None,
    type=click.Path(),
    help="Path to write resolved outputs after apply (YAML or JSON)",
)
@click.option(
    "--no-refresh",
    is_flag=True,
    default=False,
    help="Skip automatic state refresh before plan",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Fail on refresh errors instead of proceeding with stale state",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Skip interactive confirmation prompt",
)
@click.option(
    "--plan",
    "plan_file",
    default=None,
    type=click.Path(),
    help=(
        "Apply a plan previously written by 'ztf plan --out FILE'. The "
        "input + state hashes recorded in FILE are re-derived from the "
        "current input and state and apply is refused on drift unless "
        "'--force' is also passed. Skips the upfront plan() call; the "
        "summary shown comes from the plan file."
    ),
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help=(
        "Apply even when '--plan' detects that the input or state has "
        "drifted since the plan was written. Use only as a break-glass."
    ),
)
def apply(
    input: str,  # noqa: A002
    global_file: str,
    state: str,
    parallel: int | None,
    var: tuple,
    var_file: tuple,
    functions: str | None,
    output_file: str | None,
    no_refresh: bool,
    strict: bool,
    auto_approve: bool,
    plan_file: str | None,
    force: bool,
) -> None:
    """Apply changes with a confirmation prompt."""
    try:
        global_config_data = _load_config_file(global_file)
        input_config_data = _load_config_file(input)
        configure_root_logger(
            global_config_data.get("config", {}).get("debug", False),
            log_dir=os.path.dirname(os.path.abspath(input)),
        )

        var_overrides = _parse_vars(var)
        all_var_files = _collect_var_files(var_file)
        fn_map = resolve_functions_file(functions, input)
        config = load_config(
            input_config_data,
            var_overrides=var_overrides or None,
            var_files=all_var_files or None,
            functions=fn_map,
        )
        raw_state = _read_state(state)
        previous_state = raw_state
        provider = Provider(global_config_data, config, previous_state)
        _attach_run_results_path(provider, state)
        if parallel is not None:
            provider.max_workers = parallel

        effective_state = previous_state
        if not no_refresh and previous_state.get("domains"):
            try:
                logger.info("Refreshing state before apply...")
                refreshed_state = provider.refresh_state()
                _write_state(state, refreshed_state)
                provider = Provider(global_config_data, config, refreshed_state)
                _attach_run_results_path(provider, state)
                if parallel is not None:
                    provider.max_workers = parallel
                effective_state = refreshed_state
            except Exception as exc:
                if strict:
                    logger.error("Refresh failed and --strict is set: %s", exc)
                    raise SystemExit(1) from exc
                logger.warning(
                    "Failed to refresh state before apply: %s. Using existing state.",
                    exc,
                )

        if plan_file is not None:
            try:
                saved_plan = read_plan_file(plan_file)
            except PlanFileError as exc:
                logger.error("%s", exc)
                raise SystemExit(1) from exc
            click.echo(
                f"Applying plan from {plan_file} created at "
                f"{saved_plan.created_at} (ztf {saved_plan.ztf_version}, "
                f"input_hash={saved_plan.input_hash[:12]}..., "
                f"state_hash={saved_plan.state_hash[:12]}...)."
            )
            try:
                drift = verify_plan_file(
                    saved_plan,
                    current_input=config,
                    current_state=effective_state,
                    force=force,
                )
            except PlanFileError as exc:
                logger.error("%s", exc)
                raise SystemExit(1) from exc
            if drift:
                for line in drift:
                    logger.warning("Plan-file drift (--force in effect): %s", line)
            plan_result = saved_plan.operations
        else:
            plan_result = provider.plan()

        print_plan(plan_result)
        create, update, delete, operations = _count_plan_changes(plan_result)
        _print_plan_summary(create, update, delete, operations)

        known_after_apply, failed = _classify_unresolved_plan_resources(
            plan_result, config
        )
        _print_unresolved_warnings(known_after_apply, failed)

        if not any((create, update, delete, operations)):
            return

        logger.info(
            "Note: The plan above is a preview. ZTF recomputes at execution time. "
            "Infrastructure changes after this preview may alter actual operations."
        )

        if not auto_approve and not _confirm_action("apply"):
            logger.info("Apply cancelled.")
            return

        def _on_apply_state_change(s: dict) -> None:
            _write_state(state, s)

        new_state = _run_with_graceful_interrupt(
            provider, provider.run, _on_apply_state_change
        )
        _write_state(state, new_state)
        _print_run_summary(provider.run_results, label="Apply")

        interrupted = getattr(provider, "_shutdown_requested", None)
        if not (interrupted and interrupted.is_set()):
            outputs = provider.resolve_outputs()
            if outputs:
                for name, out in outputs.items():
                    logger.info("Output '%s': %s", name, out.get("value"))
                if output_file:
                    _write_outputs(output_file, outputs)

    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


def _run_with_graceful_interrupt(
    provider: Provider,
    action: Callable[..., dict[str, Any]],
    on_state_change: Callable[[dict], None],
    **action_kwargs: Any,
) -> dict[str, Any]:
    """Execute a provider action with graceful Ctrl+C handling.

    On first SIGINT the provider stops scheduling new resources and
    finishes the in-flight operation.  On second SIGINT (force quit)
    the partial state accumulated so far is returned.

    Args:
        provider: The Provider instance.
        action: Bound method to call (``provider.run`` or ``provider.destroy``).
        on_state_change: State persistence callback.
        **action_kwargs: Extra keyword arguments forwarded to *action*.

    Returns:
        Final or partial state dict.
    """
    prev_sigint = signal.getsignal(signal.SIGINT)

    def _graceful_shutdown(signum: int, frame: FrameType | None) -> None:
        provider.request_shutdown()
        logger.warning(
            "Interrupt received. Finishing current operation and "
            "saving state... (press Ctrl+C again to force quit)"
        )
        signal.signal(signal.SIGINT, prev_sigint)

    signal.signal(signal.SIGINT, _graceful_shutdown)
    try:
        return action(on_state_change=on_state_change, **action_kwargs)
    except KeyboardInterrupt:
        logger.warning("Force interrupted. Saving partial state...")
        return provider.get_partial_state()
    finally:
        signal.signal(signal.SIGINT, prev_sigint)


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------


@cli.command()
@_common_io_options
@click.option(
    "--no-refresh",
    is_flag=True,
    default=False,
    help="Skip automatic state refresh before destroy",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Fail on refresh errors instead of proceeding with stale state",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Skip interactive confirmation prompt",
)
@click.option(
    "--target",
    multiple=True,
    metavar="RESOURCE_NAME",
    help="Destroy only the named resource(s). Repeatable.",
)
def destroy(
    input: str,  # noqa: A002
    global_file: str,
    state: str,
    parallel: int | None,
    var: tuple,
    var_file: tuple,
    functions: str | None,
    no_refresh: bool,
    strict: bool,
    auto_approve: bool,
    target: tuple[str, ...],
) -> None:
    """Delete managed resources. Use --target to destroy selectively."""
    try:
        global_config_data = _load_config_file(global_file)
        input_config_data = _load_config_file(input)
        configure_root_logger(
            global_config_data.get("config", {}).get("debug", False),
            log_dir=os.path.dirname(os.path.abspath(input)),
        )

        var_overrides = _parse_vars(var)
        all_var_files = _collect_var_files(var_file)
        fn_map = resolve_functions_file(functions, input)
        config = load_config(
            input_config_data,
            var_overrides=var_overrides or None,
            var_files=all_var_files or None,
            functions=fn_map,
        )
        raw_state = _read_state(state)
        previous_state = raw_state
        provider = Provider(global_config_data, config, previous_state)
        _attach_run_results_path(provider, state)
        if parallel is not None:
            provider.max_workers = parallel

        if not no_refresh and previous_state.get("domains"):
            try:
                logger.info("Refreshing state before destroy...")
                refreshed_state = provider.refresh_state()
                _write_state(state, refreshed_state)
                provider = Provider(global_config_data, config, refreshed_state)
                _attach_run_results_path(provider, state)
                if parallel is not None:
                    provider.max_workers = parallel
            except Exception as exc:
                if strict:
                    logger.error("Refresh failed and --strict is set: %s", exc)
                    raise SystemExit(1) from exc
                logger.warning(
                    "Failed to refresh state before destroy: %s. Using existing state.",
                    exc,
                )

        destroy_map = provider.previous_domain_entity_resource_map
        if target:
            target_set = set(target)
            filtered: dict[str, dict[str, dict[str, Any]]] = {}
            for dn, entities in destroy_map.items():
                for ent, resources in entities.items():
                    for rn, rdata in resources.items():
                        if rn in target_set:
                            filtered.setdefault(dn, {}).setdefault(ent, {})[rn] = rdata
            not_found = target_set - {
                rn
                for entities in destroy_map.values()
                for resources in entities.values()
                for rn in resources
            }
            if not_found:
                logger.warning(
                    "Target resource(s) not found in state: %s",
                    ", ".join(sorted(not_found)),
                )
            destroy_map = filtered

        all_delete = _print_destroy_plan(destroy_map)
        if all_delete:
            logger.info("\nPlan: %d to destroy.", all_delete)
        else:
            logger.info("\nNo resources to destroy.")
            return

        if not auto_approve and not _confirm_action("destroy"):
            logger.info("Destroy cancelled.")
            return

        full_prev_map = provider.previous_domain_entity_resource_map
        if target:
            provider.previous_domain_entity_resource_map = destroy_map

        # Build entity_rules_map: prefer config rules, fall back to state
        entity_rules: dict[str, dict[str, dict[str, object]]] = {}
        for (
            domain_name,
            state_entities,
        ) in provider.previous_domain_entity_resource_map.items():
            domain_rules: dict[str, dict[str, object]] = {}
            domain_cfg_resources = provider.domain_entity_resource_map.get(
                domain_name, {}
            )
            for entity, state_resources in state_entities.items():
                for rname, rdata in state_resources.items():
                    cfg_rules = (
                        domain_cfg_resources.get(entity, {})
                        .get(rname, {})
                        .get("rules", {})
                    )
                    rules = cfg_rules if cfg_rules else rdata.get("rules", {})
                    if rules:
                        domain_rules.setdefault(entity, {})[rname] = rules
            entity_rules[domain_name] = domain_rules

        def _on_destroy_state_change(s: dict) -> None:
            if target:
                s = _merge_non_targeted_state(s, full_prev_map, destroy_map, raw_state)
            _write_state(state, s)

        new_state = _run_with_graceful_interrupt(
            provider,
            provider.destroy,
            _on_destroy_state_change,
            entity_rules_map=entity_rules,
        )
        if target:
            new_state = _merge_non_targeted_state(
                new_state, full_prev_map, destroy_map, raw_state
            )
        _write_state(state, new_state)
        _print_run_summary(provider.run_results, label="Destroy")

    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


def _resolve_import_entries(
    resource_name: str | None,
    domain_name: str | None,
    import_file: str | None,
) -> list[dict[str, str]]:
    """Build a list of ``{resource_name, domain_name}`` entries for import.

    Either positional arguments **or** ``--file`` must be provided, not both.

    Args:
        resource_name: Positional resource name (single-resource mode).
        domain_name: Positional domain name (single-resource mode).
        import_file: Path to a YAML bulk-import manifest.

    Returns:
        Non-empty list of import entries.

    Raises:
        click.UsageError: On conflicting or missing arguments.
    """
    if import_file and (resource_name or domain_name):
        raise click.UsageError(
            "--file cannot be combined with positional RESOURCE_NAME / DOMAIN_NAME."
        )
    if import_file:
        with open(import_file, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, list) or not data:
            raise click.UsageError(
                f"Import file '{import_file}' must contain a YAML list of "
                "{{resource_name, domain_name}} entries."
            )
        entries: list[dict[str, str]] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                raise click.UsageError(f"Entry {idx} in import file is not a mapping.")
            rn = item.get("resource_name")
            dn = item.get("domain_name")
            if not rn or not dn:
                raise click.UsageError(
                    f"Entry {idx} missing 'resource_name' or 'domain_name'."
                )
            entries.append({"resource_name": str(rn), "domain_name": str(dn)})
        return entries
    if not resource_name or not domain_name:
        raise click.UsageError(
            "Provide RESOURCE_NAME DOMAIN_NAME or use --file for bulk import."
        )
    return [{"resource_name": resource_name, "domain_name": domain_name}]


@cli.command(name="import")
@_common_io_options
@click.argument("resource_name", required=False, default=None)
@click.argument("domain_name", required=False, default=None)
@click.option(
    "--file",
    "import_file",
    default=None,
    type=click.Path(exists=True),
    help=(
        "YAML file listing resources to import in bulk. "
        "Format: list of {resource_name, domain_name} entries."
    ),
)
def import_cmd(
    input: str,  # noqa: A002
    global_file: str,
    state: str,
    parallel: int | None,
    var: tuple,
    var_file: tuple,
    functions: str | None,
    resource_name: str | None,
    domain_name: str | None,
    import_file: str | None,
) -> None:
    """Import existing resource(s) into state (Terraform-style).

    RESOURCE_NAME is the logical name defined in your input file.
    DOMAIN_NAME is the domain key in your input file.

    Alternatively use --file to bulk-import from a YAML manifest.
    """
    try:
        entries = _resolve_import_entries(resource_name, domain_name, import_file)
        provider, config, previous_state = _build_import_provider(
            global_file=global_file,
            input_file=input,
            state=state,
            var=var,
            var_file=var_file,
            functions_file=functions,
        )
        if len(entries) == 1:
            _import_single_resource(
                resource_name=entries[0]["resource_name"],
                domain_name=entries[0]["domain_name"],
                provider=provider,
                config=config,
                previous_state=previous_state,
                state_path=state,
            )
        else:
            succeeded = 0
            failed = 0
            for entry in entries:
                try:
                    _import_single_resource(
                        resource_name=entry["resource_name"],
                        domain_name=entry["domain_name"],
                        provider=provider,
                        config=config,
                        previous_state=previous_state,
                        state_path=state,
                    )
                    succeeded += 1
                except Exception as exc:
                    logger.error(
                        "Failed to import '%s' (domain '%s'): %s",
                        entry["resource_name"],
                        entry["domain_name"],
                        exc,
                    )
                    failed += 1
            logger.info(
                "\nBulk import complete: %d succeeded, %d failed.", succeeded, failed
            )
    except click.ClickException:
        raise
    except Exception as exc:
        logger.error("An error occurred: %s", exc)
        logger.debug("Traceback:", exc_info=True)
        raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# Variable / var-file helpers
# ---------------------------------------------------------------------------


def _parse_vars(var: tuple) -> dict[str, str]:
    """Parse ``--var key=value`` tuples into a dict."""
    overrides: dict[str, str] = {}
    for v in var:
        k, val = parse_var_string(v)
        overrides[k] = val
    return overrides


def _collect_var_files(var_file: tuple) -> list[str]:
    """Merge auto-loaded ztfvars files with explicit ``--var-file`` paths.

    Raises:
        FileNotFoundError: If an explicit var file does not exist.
        IsADirectoryError: If an explicit var file path is a directory.
    """
    for vf in var_file:
        _validate_file_path(vf, "Variable file")
    auto = discover_auto_var_files()
    if auto:
        for avf in auto:
            logger.info("Auto-loading variable file: %s", avf)
    return auto + list(var_file)


# ---------------------------------------------------------------------------
# Legacy entry point (kept for python -m ztf.main compatibility)
# ---------------------------------------------------------------------------


def main() -> None:
    """Legacy entry point — delegates to the Click CLI."""
    cli()


if __name__ == "__main__":
    cli()
