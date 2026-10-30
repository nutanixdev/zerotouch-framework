"""Guard against drift between the two dev-dependency declarations.

``pyproject.toml`` intentionally declares the dev dependency list twice:

* ``[project.optional-dependencies].dev`` -- consumed by ``pip install
  .[dev]`` and the CI workflows that use ``uv pip install -e ".[dev]"``.
* ``[dependency-groups].dev`` (PEP 735) -- consumed by ``uv sync`` as the
  default dev group for contributors working with uv natively.

The two lists MUST be identical; if one is updated without the other,
``pip``-based and ``uv sync``-based environments silently diverge. This
test fails fast so the mismatch is caught in review rather than in
production.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ``tomllib`` is stdlib on Python 3.11+; on 3.10 the drift check is
# skipped rather than pulling in a backport dev dependency just for
# this single consistency test.
tomllib = pytest.importorskip("tomllib")

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """Parse pyproject.toml once per test module."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_dev_dependency_lists_are_in_sync(pyproject: dict) -> None:
    """``[project.optional-dependencies].dev`` must match ``[dependency-groups].dev``."""
    optional_dev = (
        pyproject.get("project", {}).get("optional-dependencies", {}).get("dev")
    )
    group_dev = pyproject.get("dependency-groups", {}).get("dev")

    assert optional_dev is not None, (
        "[project.optional-dependencies].dev is missing from pyproject.toml"
    )
    assert group_dev is not None, (
        "[dependency-groups].dev is missing from pyproject.toml"
    )

    # Compare as sorted lists: order is not semantically meaningful for
    # dependency specifiers, but the two sources must contain the same
    # set of specifier strings (version pins included).
    optional_sorted = sorted(optional_dev)
    group_sorted = sorted(group_dev)

    assert optional_sorted == group_sorted, (
        "Dev dependency lists have drifted between "
        "[project.optional-dependencies].dev and [dependency-groups].dev.\n"
        f"  optional-only: {sorted(set(optional_sorted) - set(group_sorted))}\n"
        f"  group-only:    {sorted(set(group_sorted) - set(optional_sorted))}\n"
        "Update both sections in pyproject.toml so they match."
    )
