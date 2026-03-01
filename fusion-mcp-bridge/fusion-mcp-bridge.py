"""
Fusion MCP Bridge

A generic Fusion 360 add-in that bridges external MCP servers to the
Fusion Python SDK over a local TCP socket. Any MCP server can send
Python scripts to be executed on the Fusion main thread.

Architecture:
    - TCP server runs in a background thread (tcp_server.py)
    - Incoming requests are dispatched to the main thread via CustomEvent
    - A queue + WorkItem pattern decouples TCP threads from the main thread
    - A backup timer fires the custom event every 200ms for reliability
    - The executor runs arbitrary Python with adsk.* available (executor.py)
    - Results are passed back to the TCP thread and sent as JSON responses

All business logic lives on the MCP server side. The bridge is a thin
"run this code on the main thread" proxy.
"""

import adsk.core
import adsk.fusion
import adsk.cam
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

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

# ──────────────────────────────────────────────────────────────────────
# File-based logging (alongside Fusion's app.log)
# ──────────────────────────────────────────────────────────────────────

LOG_PATH = Path.home() / "fusion-mcp-bridge.log"

def _setup_logging():
    logger = logging.getLogger("fusion_mcp_bridge")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
    return logger

_file_logger = _setup_logging()

# Custom event ID for marshaling requests to the main thread
CUSTOM_EVENT_ID = "FusionMcpBridgeRequestEvent"

# Backup timer interval — fires CustomEvent periodically in case
# fireCustomEvent() from a daemon thread is silently dropped.
_TIMER_INTERVAL_S = 0.2

# Global references (must stay in scope for Fusion's garbage collector)
_app = None
_ui = None
_tcp_server = None
_custom_event = None
_custom_event_handler = None
_handlers = []

# Queue-based dispatch: each request gets a WorkItem with its own Event
_work_queue = queue.Queue()
_timer_running = False
_timer_thread = None


class WorkItem:
    """One unit of work submitted from a TCP thread for main-thread execution."""
    __slots__ = ("request", "response", "error", "done")

    def __init__(self, request):
        self.request = request
        self.response = None
        self.error = None
        self.done = threading.Event()


def log(msg):
    """Log to both Fusion's text commands palette and the log file."""
    _file_logger.info(msg)
    try:
        app = adsk.core.Application.get()
        app.log(f"[MCP-Bridge] {msg}")
    except Exception:
        pass


class MainThreadEventHandler(adsk.core.CustomEventHandler):
    """
    Handles the custom event fired from TCP background threads or the
    backup timer. Runs on the Fusion main thread, so adsk.* API calls
    are safe. Drains the entire work queue on each invocation.
    """

    def __init__(self):
        super().__init__()

    def notify(self, args):
        _drain_queue()


def _drain_queue():
    """Execute every queued WorkItem (must be called on the main thread)."""
    while True:
        try:
            item = _work_queue.get_nowait()
        except queue.Empty:
            break

        try:
            item.response = execute_request(item.request)
        except Exception:
            item.error = f"Main thread error: {traceback.format_exc()}"
            _file_logger.error("Main-thread exec raised: %s", item.error)
        finally:
            item.done.set()


def dispatch_to_main_thread(request):
    """
    Called from TCP background threads. Queues the request for main-thread
    execution and blocks until the result is ready.
    """
    if request.get("action") == "ping":
        return {"success": True, "data": {"status": "ok", "message": "Fusion MCP Bridge is running"}}

    item = WorkItem(request)
    _work_queue.put(item)

    try:
        app = adsk.core.Application.get()
        app.fireCustomEvent(CUSTOM_EVENT_ID)
    except Exception:
        pass  # backup timer will pick it up

    if not item.done.wait(timeout=30.0):
        _file_logger.warning("Request timed out after 30s")
        return {"success": False, "error": "Timeout waiting for main thread response"}

    if item.error is not None:
        return {"success": False, "error": item.error}
    return item.response


def _timer_loop():
    """Backup timer: fires the custom event every 200ms while work is pending."""
    while _timer_running:
        time.sleep(_TIMER_INTERVAL_S)
        if not _work_queue.empty():
            try:
                app = adsk.core.Application.get()
                app.fireCustomEvent(CUSTOM_EVENT_ID)
            except Exception:
                pass


def run(context):
    """Called when the add-in is started."""
    global _app, _ui, _tcp_server, _custom_event, _custom_event_handler
    global _timer_running, _timer_thread

    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        # Register custom event for main-thread dispatch
        _custom_event = _app.registerCustomEvent(CUSTOM_EVENT_ID)
        _custom_event_handler = MainThreadEventHandler()
        _custom_event.add(_custom_event_handler)
        _handlers.append(_custom_event_handler)

        # Start the backup timer
        _timer_running = True
        _timer_thread = threading.Thread(target=_timer_loop, daemon=True)
        _timer_thread.start()

        # Start the TCP server
        _tcp_server = JsonTcpServer(
            request_callback=dispatch_to_main_thread,
            logger=log
        )
        _tcp_server.start()

        log(f"Fusion MCP Bridge started (port {_tcp_server.port}, log: {LOG_PATH})")

    except Exception:
        _file_logger.exception("Failed to start Fusion MCP Bridge")
        if _ui:
            _ui.messageBox(f"Fusion MCP Bridge failed to start:\n{traceback.format_exc()}")


def stop(context):
    """Called when the add-in is stopped."""
    global _app, _ui, _tcp_server, _custom_event, _custom_event_handler
    global _timer_running, _timer_thread

    try:
        # Stop the backup timer
        _timer_running = False
        if _timer_thread:
            _timer_thread.join(timeout=1.0)
            _timer_thread = None

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
        _file_logger.exception("Failed to stop Fusion MCP Bridge cleanly")
        if _ui:
            _ui.messageBox(f"Fusion MCP Bridge failed to stop cleanly:\n{traceback.format_exc()}")
