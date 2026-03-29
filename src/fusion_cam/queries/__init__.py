"""
Query script loader for the Fusion CAM CLI.

Loads Python query scripts from this directory and prepends shared helpers.
Helper modules are any files matching `_*.py` (sorted alphabetically),
which ensures correct dependency order (_1_base before _2_params, etc.).

Scripts are cached in memory for the lifetime of one CLI process. Each new
`fusion-cam` invocation reloads from disk (no Fusion add-in restart needed).
"""

import os

_QUERIES_DIR = os.path.dirname(os.path.abspath(__file__))

# Cache: script name -> combined code string (helpers + query)
_cache: dict[str, str] = {}

# Helpers code is loaded once and prepended to every query
_helpers_code: str | None = None


def _read_file(filename: str) -> str:
    """Read a file from the queries directory."""
    path = os.path.join(_QUERIES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _get_helpers() -> str:
    """Load and cache the shared helpers code from all _*.py files."""
    global _helpers_code
    if _helpers_code is None:
        helper_files = sorted(
            f for f in os.listdir(_QUERIES_DIR)
            if f.startswith("_") and f.endswith(".py") and f != "__init__.py"
        )
        _helpers_code = "\n\n".join(_read_file(f) for f in helper_files)
    return _helpers_code


def get_helpers_code() -> str:
    """Return shared query helper sources (for debug / ad-hoc bridge scripts)."""
    return _get_helpers()


def load_query(name: str, params: dict | None = None) -> dict:
    """
    Load a query script by name and build the execute request.

    The helpers code is prepended to the query script so that all shared
    constants and utility functions are available.

    Args:
        name: Query script name (without .py extension),
              e.g. "get_setups", "get_operations".
        params: Optional parameters dict passed to the script
                as the `params` variable.

    Returns:
        dict ready to send via FusionClient.send_request():
        {"action": "execute", "code": "...", "params": {...}}
    """
    if name not in _cache:
        helpers = _get_helpers()
        query = _read_file(f"{name}.py")
        _cache[name] = helpers + "\n\n" + query

    return {
        "action": "execute",
        "code": _cache[name],
        "params": params or {},
    }
