"""
Fusion MCP Bridge

A generic Fusion 360 add-in that bridges external MCP servers to the
Fusion Python SDK over a local TCP socket. Any MCP server can send
Python scripts to be executed on the Fusion main thread.

Architecture:
    - TCP server runs in a background thread (tcp_server.py)
    - Incoming requests are dispatched to the main thread via CustomEvent
    - The executor runs arbitrary Python with adsk.* available (executor.py)
    - Results are passed back to the TCP thread and sent as JSON responses

All business logic lives on the MCP server side. The bridge is a thin
"run this code on the main thread" proxy.
"""

import adsk.core
import adsk.fusion
import adsk.cam
import json
import os
import sys
import threading
import traceback

# Add the add-in directory to sys.path so we can import our modules
ADDIN_DIR = os.path.dirname(os.path.abspath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

# Force-reload our modules so that code changes take effect on add-in restart
# without needing to restart Fusion 360 entirely.
import importlib
for _mod_name in ["tcp_server", "executor"]:
    if _mod_name in sys.modules:
        importlib.reload(sys.modules[_mod_name])

from tcp_server import JsonTcpServer
from executor import execute_request

# Custom event ID for marshaling requests to the main thread
CUSTOM_EVENT_ID = "FusionMcpBridgeRequestEvent"

# Global references (must stay in scope for Fusion's garbage collector)
_app = None
_ui = None
_tcp_server = None
_custom_event = None
_custom_event_handler = None
_handlers = []

# Threading primitives for main-thread dispatch
_pending_request = None
_pending_response = None
_response_ready = threading.Event()
_dispatch_lock = threading.Lock()


def log(msg):
    """Log a message to the Fusion 360 text commands palette."""
    try:
        app = adsk.core.Application.get()
        app.log(f"[MCP-Bridge] {msg}")
    except Exception:
        pass


class MainThreadEventHandler(adsk.core.CustomEventHandler):
    """
    Handles the custom event fired from the TCP background thread.
    This runs on the Fusion main thread, so it is safe to call adsk.* APIs.
    """

    def __init__(self):
        super().__init__()

    def notify(self, args):
        global _pending_response, _pending_request
        try:
            event_args = adsk.core.CustomEventArgs.cast(args)

            # The request dict was stored in the global before firing the event
            request = _pending_request
            if request is None:
                _pending_response = {"success": False, "error": "No pending request"}
                _response_ready.set()
                return

            # Execute the request on the main thread
            _pending_response = execute_request(request)

        except Exception:
            _pending_response = {
                "success": False,
                "error": f"Main thread error: {traceback.format_exc()}"
            }
        finally:
            _response_ready.set()


def dispatch_to_main_thread(request):
    """
    Called from the TCP background thread.
    Fires a CustomEvent to run the handler on the main thread,
    then blocks until the response is ready.

    A lock serializes concurrent requests so that the shared globals
    (_pending_request / _pending_response / _response_ready) are never
    corrupted by interleaved TCP client threads.
    """
    global _pending_request, _pending_response

    # Ping is handled directly without main thread dispatch
    if request.get("action") == "ping":
        return {"success": True, "data": {"status": "ok", "message": "Fusion MCP Bridge is running"}}

    with _dispatch_lock:
        _response_ready.clear()
        _pending_request = request
        _pending_response = None

        try:
            app = adsk.core.Application.get()
            app.fireCustomEvent(CUSTOM_EVENT_ID, json.dumps(request))
        except Exception:
            return {"success": False, "error": f"Failed to fire custom event: {traceback.format_exc()}"}

        # Wait for the main thread handler to complete (timeout 30s)
        if not _response_ready.wait(timeout=30.0):
            return {"success": False, "error": "Timeout waiting for main thread response"}

        return _pending_response


def run(context):
    """Called when the add-in is started."""
    global _app, _ui, _tcp_server, _custom_event, _custom_event_handler

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Register custom event for main-thread dispatch
        _custom_event = _app.registerCustomEvent(CUSTOM_EVENT_ID)
        _custom_event_handler = MainThreadEventHandler()
        _custom_event.add(_custom_event_handler)
        _handlers.append(_custom_event_handler)

        # Start the TCP server
        _tcp_server = JsonTcpServer(
            request_callback=dispatch_to_main_thread,
            logger=log
        )
        _tcp_server.start()

        log(f"Fusion MCP Bridge started (port {_tcp_server.port})")

    except Exception:
        if _ui:
            _ui.messageBox(f"Fusion MCP Bridge failed to start:\n{traceback.format_exc()}")


def stop(context):
    """Called when the add-in is stopped."""
    global _app, _ui, _tcp_server, _custom_event, _custom_event_handler

    try:
        # Stop the TCP server
        if _tcp_server:
            _tcp_server.stop()
            _tcp_server = None

        # Unregister custom event
        if _custom_event:
            _app.unregisterCustomEvent(CUSTOM_EVENT_ID)
            _custom_event = None
            _custom_event_handler = None

        _handlers.clear()

        log("Fusion MCP Bridge stopped")

    except Exception:
        if _ui:
            _ui.messageBox(f"Fusion MCP Bridge failed to stop cleanly:\n{traceback.format_exc()}")
