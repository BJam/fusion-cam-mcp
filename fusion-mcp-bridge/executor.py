"""
Generic Python script executor for the Fusion MCP Bridge.

Replaces the handler-per-action pattern (cam_handler.py) with a thin
exec() engine. The MCP server sends Python scripts over TCP; this module
executes them on the Fusion main thread with the adsk SDK available in
the namespace.

All business logic now lives on the MCP server side in queries/*.py.
The addin is just a "run this code on the main thread" proxy.
"""

import adsk.core
import adsk.fusion
import adsk.cam
import traceback


def execute_request(request):
    """
    Execute a request on the Fusion main thread.

    Supported actions:
        - "ping": health check, returns immediately.
        - "execute": runs the provided Python code with adsk modules
          and a params dict available in the namespace. Scripts may
          either define a ``def run(params)`` function (preferred) or
          set the ``result`` variable directly (legacy).

    Args:
        request: dict with "action" and optionally "code" / "params".

    Returns:
        dict with "success" (bool) and "data" or "error".
    """
    action = request.get("action", "")

    if action == "ping":
        return {"success": True, "data": {"status": "ok"}}

    if action == "execute":
        # The FusionClient sends {"action": "execute", "params": {"code": ..., "params": ...}}
        # so the code and script params are nested under request["params"].
        payload = request.get("params", {})
        code = payload.get("code", "")
        params = payload.get("params", {})

        if not code:
            return {"success": False, "error": "No code provided in 'execute' request"}

        # Build the execution namespace with Fusion SDK modules available
        namespace = {
            # Fusion SDK top-level modules
            "adsk": adsk,
            # Input parameters from the MCP server
            "params": params,
            # The script sets this to its return value
            "result": None,
        }

        try:
            exec(code, namespace)
        except Exception:
            return {
                "success": False,
                "error": f"Script execution error:\n{traceback.format_exc()}"
            }

        # Preferred path: script defines a run(params) function
        run_fn = namespace.get("run")
        if callable(run_fn):
            try:
                namespace["result"] = run_fn(params)
            except Exception:
                return {
                    "success": False,
                    "error": f"Script execution error:\n{traceback.format_exc()}"
                }

        result = namespace.get("result")
        if result is None:
            return {
                "success": False,
                "error": "Script completed but did not set 'result'. "
                         "Define a run(params) function or assign to the 'result' variable."
            }

        # If the script returned an error dict from a helper function
        # (e.g. _get_cam() returning {"success": False, "error": "..."}),
        # propagate it directly instead of wrapping in another success envelope.
        if isinstance(result, dict) and result.get("success") is False:
            return result

        return {"success": True, "data": result}

    return {
        "success": False,
        "error": f"Unknown action: '{action}'. Supported actions: ['ping', 'execute']"
    }
