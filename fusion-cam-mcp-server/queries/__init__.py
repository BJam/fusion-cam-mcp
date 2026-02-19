"""
Query script loader for the Fusion 360 CAM MCP server.

Loads Python query scripts from this directory and prepends shared helpers.
Scripts are cached in memory after first load. To iterate on query logic,
edit the script file and restart the MCP server (no Fusion addin restart needed).
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
    """Load and cache the shared helpers code."""
    global _helpers_code
    if _helpers_code is None:
        _helpers_code = _read_file("_helpers.py")
    return _helpers_code


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
