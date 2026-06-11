"""Plan-file persistence for ``ztf plan --out`` / ``ztf apply --plan``.

A plan file captures everything ``ztf apply`` needs to confirm that a
previously-reviewed plan still applies safely:

* the **operations** dict produced by :meth:`Provider.plan`
* an **input hash** (sha256 of the canonical-JSON resolved config)
* a **state hash** (sha256 of the canonical-JSON loaded state)
* the ZTF version and a schema version for forward compatibility

The serialized format is canonical JSON (orjson with sorted keys) so a
``plan --out`` followed by an immediate ``plan --out`` against the same
inputs produces byte-identical files, which is the property the team
workflow relies on for peer review and audit.

When ``apply --plan`` runs, :func:`verify_plan_file` re-derives both
hashes from the current input + state and refuses to apply on mismatch
unless the operator overrides with ``--force``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson

import ztf

#: Bumped whenever the plan-file schema changes in a non-backward-compatible
#: way.  Apply refuses to consume a file with a different schema version.
PLAN_FILE_SCHEMA_VERSION: int = 1


class PlanFileError(Exception):
    """Raised when a plan file cannot be parsed, verified, or applied."""


@dataclass(frozen=True)
class PlanFile:
    """In-memory representation of a serialized plan file."""

    schema_version: int
    ztf_version: str
    created_at: str
    input_hash: str
    state_hash: str
    operations: dict[str, Any]


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _canonical_json(payload: Any) -> bytes:
    """Serialize *payload* to canonical (sorted-keys) JSON bytes.

    Uses :mod:`orjson` per project rules.  ``OPT_SORT_KEYS`` guarantees
    that dicts with the same logical content produce identical bytes
    regardless of insertion order, which is what makes the plan-file
    hashes deterministic.

    ``OPT_NON_STR_KEYS`` is set so resource maps containing integer or
    other non-string keys (rare but legal in plan output) don't raise.
    """
    return orjson.dumps(
        payload,
        option=orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS,
        default=str,
    )


def hash_payload(payload: Any) -> str:
    """Return the sha256 hex digest of *payload* as canonical JSON.

    Suitable for the ``input_hash`` and ``state_hash`` fields of the
    plan file.  ``str`` is used as the orjson fallback so non-JSON-able
    objects (paths, sets) hash by their string repr rather than raising.
    """
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


#: Top-level keys excluded from the input hash because their contents
#: are not stable across CLI invocations even when the user-facing
#: config is unchanged. ``functions`` carries live Python callables
#: whose ``repr`` includes the memory address; the function bodies they
#: reference don't appear in input.yml at all so their identity is not
#: a property the operator reviewed.
_INPUT_HASH_EXCLUDED_KEYS: frozenset[str] = frozenset({"functions"})


def hash_input_config(config: Any) -> str:
    """Hash a resolved input config, excluding non-reproducible fields.

    Wrapper around :func:`hash_payload` that removes keys whose value
    representations differ across CLI invocations even when the user's
    input.yml is byte-identical (currently: the ``functions`` map of
    loaded Python callables).
    """
    if isinstance(config, dict):
        sanitized = {
            k: v for k, v in config.items() if k not in _INPUT_HASH_EXCLUDED_KEYS
        }
        return hash_payload(sanitized)
    return hash_payload(config)


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def write_plan_file(
    path: str | Path,
    *,
    operations: dict[str, Any],
    input_config: Any,
    state_data: Any,
    created_at: datetime | None = None,
) -> PlanFile:
    """Serialize a plan to *path* with byte-stable canonical JSON.

    Args:
        path: Destination file (parent dirs are created if missing).
        operations: ``Provider.plan()`` output -- the create/update/
            delete/operations dict.
        input_config: The resolved input config dict; used to derive
            ``input_hash``.
        state_data: The loaded state dict; used to derive ``state_hash``.
        created_at: Override timestamp (test hook).  Defaults to
            ``datetime.now(timezone.utc)``.

    Returns:
        The :class:`PlanFile` that was persisted, useful for logging the
        hashes back to the operator.
    """
    plan = PlanFile(
        schema_version=PLAN_FILE_SCHEMA_VERSION,
        ztf_version=ztf.__version__,
        created_at=(created_at or datetime.now(timezone.utc)).isoformat(),
        input_hash=hash_input_config(input_config),
        state_hash=hash_payload(state_data),
        operations=operations,
    )
    payload: dict[str, Any] = {
        "schema_version": plan.schema_version,
        "ztf_version": plan.ztf_version,
        "created_at": plan.created_at,
        "input_hash": plan.input_hash,
        "state_hash": plan.state_hash,
        "operations": plan.operations,
    }
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(_canonical_json(payload))
    return plan


def read_plan_file(path: str | Path) -> PlanFile:
    """Load and validate the structural shape of a plan file.

    Schema-version compatibility is checked here so a wrong-version file
    fails fast with a clear message before any apply work begins.

    Raises:
        PlanFileError: If the file is missing, malformed, or written by
            an incompatible schema version.
    """
    src = Path(path)
    if not src.is_file():
        raise PlanFileError(f"Plan file not found: {src}")
    try:
        payload = orjson.loads(src.read_bytes())
    except orjson.JSONDecodeError as exc:
        raise PlanFileError(f"Plan file '{src}' is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise PlanFileError(
            f"Plan file '{src}' must contain a JSON object at the top level."
        )

    required = (
        "schema_version",
        "ztf_version",
        "created_at",
        "input_hash",
        "state_hash",
        "operations",
    )
    missing = [k for k in required if k not in payload]
    if missing:
        raise PlanFileError(
            f"Plan file '{src}' is missing required field(s): {', '.join(missing)}."
        )

    schema_version = payload["schema_version"]
    if schema_version != PLAN_FILE_SCHEMA_VERSION:
        raise PlanFileError(
            f"Plan file '{src}' has schema_version={schema_version}; this "
            f"build of ztf only understands version "
            f"{PLAN_FILE_SCHEMA_VERSION}. Re-run 'ztf plan --out' with the "
            "current ztf version to regenerate it."
        )

    operations = payload["operations"]
    if not isinstance(operations, dict):
        raise PlanFileError(f"Plan file '{src}' has a non-object 'operations' field.")

    return PlanFile(
        schema_version=int(schema_version),
        ztf_version=str(payload["ztf_version"]),
        created_at=str(payload["created_at"]),
        input_hash=str(payload["input_hash"]),
        state_hash=str(payload["state_hash"]),
        operations=operations,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_plan_file(
    plan: PlanFile,
    *,
    current_input: Any,
    current_state: Any,
    force: bool = False,
) -> list[str]:
    """Compare a plan file against the current input + state.

    Args:
        plan: The previously-loaded plan file.
        current_input: The freshly-resolved input config.
        current_state: The freshly-loaded state dict.
        force: If ``True``, drift is reported but not fatal -- callers
            log the warnings and continue.  This is the
            ``--force`` escape hatch for break-glass scenarios.

    Returns:
        A list of human-readable drift descriptions.  Empty when both
        hashes match.

    Raises:
        PlanFileError: When drift is detected and *force* is ``False``.
    """
    drift: list[str] = []
    current_input_hash = hash_input_config(current_input)
    current_state_hash = hash_payload(current_state)

    if current_input_hash != plan.input_hash:
        drift.append(
            f"Input config hash drift: plan recorded {plan.input_hash[:12]}..., "
            f"current is {current_input_hash[:12]}.... The input.yml has "
            "changed since the plan was produced."
        )
    if current_state_hash != plan.state_hash:
        drift.append(
            f"State hash drift: plan recorded {plan.state_hash[:12]}..., "
            f"current is {current_state_hash[:12]}.... The state file has "
            "changed since the plan was produced (concurrent apply or "
            "manual edit?)."
        )

    if drift and not force:
        joined = "\n  - ".join(drift)
        raise PlanFileError(
            "Plan file no longer matches current inputs:\n  - "
            f"{joined}\n"
            "Re-run 'ztf plan --out' to refresh the plan, or pass "
            "'--force' to apply anyway (not recommended)."
        )
    return drift
