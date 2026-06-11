"""Loader for user-defined ``{fn.*}`` functions.

Discovers and imports a user-supplied Python file (typically
``functions.py`` next to ``input.yml``).  Every public callable in that
file becomes available as a ``{fn.<name>(<args>)}`` interpolation token.

Third-party imports inside the user file must be installed in the same
Python environment where ZTF runs.  Stdlib modules (``csv``, ``json``,
``base64``, etc.) are always available.
"""

import hashlib
import importlib.util
import inspect
import os
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ztf.utils.utils import get_logger

logger = get_logger(__name__)


def load_functions(path: str | Path) -> dict[str, Callable[..., Any]]:
    """Import a Python file and return its public callables as a dict.

    Args:
        path: Filesystem path to the user functions file.

    Returns:
        ``{name: callable}`` for every public, non-dunder function
        defined at module level (classes and other callables are excluded).

    Raises:
        FileNotFoundError: If *path* does not exist.
        ImportError: If the file cannot be imported.
    """
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Functions file not found: {resolved}")

    # Disambiguate the module name per resolved path so loading two
    # different ``functions.py`` files in the same process (REPL,
    # tests, orchestration scripts) does not cause the ``__module__``
    # attribute of user-defined functions to collide.  SHA-256 is used
    # for its ubiquity, not for security; ``usedforsecurity=False``
    # keeps Bandit and FIPS-restricted environments happy.
    path_digest = hashlib.sha256(
        str(resolved).encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]
    module_name = f"ztf_user_functions_{path_digest}"

    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create import spec for: {resolved}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    functions: dict[str, Callable[..., Any]] = {}
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        if isinstance(obj, types.ModuleType):
            continue
        if not (inspect.isfunction(obj) or inspect.isbuiltin(obj)):
            continue
        # Exclude callables imported from other modules
        # (e.g. ``from math import sqrt``) so the dict only contains
        # functions actually defined in the user's file, matching the
        # documented contract.
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        functions[name] = obj

    if functions:
        logger.info(
            "Loaded %d function(s) from %s: %s",
            len(functions),
            resolved,
            ", ".join(sorted(functions)),
        )

    return functions


def discover_functions_file(config_dir: str | Path) -> str | None:
    """Auto-discover a ``functions.py`` file near the config directory.

    Search order:

    1. *config_dir* itself (e.g. ``config/categories/``).
    2. Parent of *config_dir* (e.g. ``config/``).
    3. ``examples/`` relative to the working directory (where
       ``ztf examples`` places a starter file).

    Args:
        config_dir: Directory to search (typically the directory
            containing ``input.yml``).

    Returns:
        Absolute path to the discovered file, or ``None`` if not found.
    """
    search_dirs = [
        Path(config_dir),
        Path(config_dir).parent,
        Path.cwd() / "examples",
    ]
    for directory in search_dirs:
        candidate = directory / "functions.py"
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def resolve_functions_file(
    explicit_path: str | None,
    input_file: str,
) -> dict[str, Callable[..., Any]]:
    """Load user functions from an explicit path or auto-discovered file.

    Args:
        explicit_path: Path from ``--functions`` CLI flag, or ``None``.
        input_file: Path to the input YAML file (used for auto-discovery).

    Returns:
        Dict of loaded functions (may be empty if no file found).
    """
    if explicit_path:
        return load_functions(explicit_path)

    config_dir = os.path.dirname(os.path.abspath(input_file))
    discovered = discover_functions_file(config_dir)
    if discovered:
        return load_functions(discovered)

    return {}
