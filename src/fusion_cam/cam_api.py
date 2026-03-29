"""
Shared Fusion 360 CAM bridge operations for the CLI.

All responses use the structured envelope:
  {"success": true, "data": ...} on success
  {"success": false, "error": "...", "code": "..."} on failure
"""

from __future__ import annotations

from typing import Any

from .fusion_client import FusionClient
from .queries import load_query

READ_ONLY_ERROR = (
    "Write operations (updating parameters, assigning materials, etc.) are not "
    "available in read-only mode.\n\n"
    "To enable them, run with --mode full (or set FUSION_CAM_MODE=full)."
)


def bridge_ping(client: FusionClient) -> dict[str, Any]:
    try:
        return client.send_request("ping")
    except ConnectionError as e:
        return {"success": False, "error": str(e), "code": "CONNECTION_ERROR"}
    except Exception as e:
        return {"success": False, "error": str(e), "code": "INTERNAL_ERROR"}


def bridge_execute_query(
    client: FusionClient, query_name: str, params: dict | None = None
) -> dict[str, Any]:
    """Load a named query from queries/ and run it on the bridge."""
    request = load_query(query_name, params)
    try:
        return client.send_request(
            request["action"],
            {"code": request["code"], "params": request["params"]},
        )
    except ConnectionError as e:
        return {"success": False, "error": str(e), "code": "CONNECTION_ERROR"}
    except Exception as e:
        return {"success": False, "error": str(e), "code": "INTERNAL_ERROR"}


def bridge_execute_raw(
    client: FusionClient,
    code: str,
    params: dict | None = None,
) -> dict[str, Any]:
    """Run arbitrary Python on the Fusion main thread (debug / advanced)."""
    try:
        return client.send_request(
            "execute",
            {"code": code, "params": params or {}},
        )
    except ConnectionError as e:
        return {"success": False, "error": str(e), "code": "CONNECTION_ERROR"}
    except Exception as e:
        return {"success": False, "error": str(e), "code": "INTERNAL_ERROR"}


class CamSession:
    """One FusionClient + CLI mode (read-only vs full)."""

    def __init__(self, mode: str):
        self.mode = mode
        self.client = FusionClient()

    def close(self) -> None:
        self.client.close()

    def require_write(self) -> dict[str, Any] | None:
        if self.mode != "full":
            return {"success": False, "error": READ_ONLY_ERROR, "code": "READ_ONLY"}
        return None

    def ping(self) -> dict[str, Any]:
        return bridge_ping(self.client)

    def query(
        self, name: str, params: dict | None = None, *, write: bool = False
    ) -> dict[str, Any]:
        if write:
            blocked = self.require_write()
            if blocked is not None:
                return blocked
        return bridge_execute_query(self.client, name, params or {})

    def debug(
        self,
        code: str,
        params: dict | None = None,
        *,
        prepend_helpers: bool = False,
        helpers_source: str | None = None,
    ) -> dict[str, Any]:
        final = code
        if prepend_helpers and helpers_source:
            final = helpers_source.rstrip() + "\n\n" + code
        return bridge_execute_raw(self.client, final, params)
