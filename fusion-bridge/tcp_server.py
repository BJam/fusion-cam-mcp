"""
TCP server for the Fusion bridge add-in.

Runs a TCP listener in a background thread. Each incoming request is a
newline-delimited JSON object. The request is dispatched to a handler
on the Fusion main thread via CustomEvent, and the JSON response is
sent back over the socket.

The server auto-restarts on transient socket errors (bind failure,
accept crash) up to a configurable maximum number of retries.
"""

import json
import os
import socket
import threading
import time
import traceback


# Default port, overridable via environment variable
DEFAULT_PORT = 9876

# Auto-restart configuration
_RESTART_DELAY = 2.0   # seconds between bind retries
_MAX_RESTARTS = 10      # consecutive failures before giving up


def get_port():
    """Return the configured TCP port (FUSION_CAM_BRIDGE_PORT, else legacy FUSION_CAM_MCP_PORT)."""
    for key in ("FUSION_CAM_BRIDGE_PORT", "FUSION_CAM_MCP_PORT"):
        raw = os.environ.get(key)
        if raw is not None and raw != "":
            try:
                return int(raw)
            except (ValueError, TypeError):
                continue
    return DEFAULT_PORT


class JsonTcpServer:
    """
    A TCP server that accepts multiple concurrent connections,
    reads newline-delimited JSON requests, and sends JSON responses.

    Each client connection is handled in its own thread. The actual
    request handling is delegated to a callback that runs on the
    Fusion main thread via CustomEvent (which serializes API access).

    If the listening socket dies (bind failure, accept crash), the
    server automatically retries up to _MAX_RESTARTS times before
    giving up.
    """

    def __init__(self, request_callback, logger=None):
        """
        Args:
            request_callback: callable(dict) -> dict
                Called for each JSON request. Must return a dict to send back.
                This will be invoked from the background thread; it is the
                caller's responsibility to marshal onto the main thread.
            logger: callable(str) or None
                Optional logging function.
        """
        self._request_callback = request_callback
        self._log = logger or (lambda msg: None)
        self._server_socket = None
        self._thread = None
        self._running = False
        self._port = get_port()
        self._client_threads = []
        self._client_sockets = []
        self._clients_lock = threading.Lock()

    @property
    def port(self):
        return self._port

    def start(self):
        """Start the TCP server in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._serve_with_restart, daemon=True)
        self._thread.start()
        self._log(f"TCP server started on localhost:{self._port}")

    def stop(self):
        """Stop the TCP server and close all client connections."""
        self._running = False

        # Close all active client sockets to unblock their recv() calls
        with self._clients_lock:
            for cs in self._client_sockets:
                try:
                    cs.close()
                except Exception:
                    pass
            self._client_sockets.clear()

        # Close the server socket to unblock accept()
        self._close_server_socket()

        # Wait for client threads to finish
        for t in self._client_threads:
            t.join(timeout=2.0)
        self._client_threads.clear()

        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

        self._log("TCP server stopped")

    def _close_server_socket(self):
        """Close the listening socket if open."""
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

    def _bind_and_listen(self):
        """Create, bind, and listen. Returns True on success."""
        self._close_server_socket()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(1.0)  # Allow periodic checks of _running
            s.bind(("127.0.0.1", self._port))
            s.listen(5)
            self._server_socket = s
            self._log(f"TCP server listening on localhost:{self._port}")
            return True
        except Exception:
            self._log(f"TCP bind failed: {traceback.format_exc()}")
            self._close_server_socket()
            return False

    def _serve_with_restart(self):
        """Outer loop: re-binds the socket on failure, up to _MAX_RESTARTS times."""
        restarts = 0

        while self._running:
            if not self._bind_and_listen():
                restarts += 1
                if restarts > _MAX_RESTARTS:
                    self._log(
                        f"TCP server exceeded {_MAX_RESTARTS} restart attempts — giving up"
                    )
                    break
                self._log(
                    f"Retrying bind in {_RESTART_DELAY}s "
                    f"(attempt {restarts}/{_MAX_RESTARTS})"
                )
                time.sleep(_RESTART_DELAY)
                continue

            restarts = 0

            try:
                self._accept_loop()
            except Exception:
                if self._running:
                    self._log(f"Accept loop crashed: {traceback.format_exc()}")

            if self._running:
                self._log(f"Socket lost — restarting in {_RESTART_DELAY}s")
                self._close_server_socket()
                time.sleep(_RESTART_DELAY)

    def _accept_loop(self):
        """Inner loop: accepts clients until the socket errors out."""
        while self._running:
            try:
                client_socket, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    raise
                break

            self._log(f"Client connected from {addr}")

            with self._clients_lock:
                self._client_sockets.append(client_socket)

            client_thread = threading.Thread(
                target=self._handle_client_thread,
                args=(client_socket, addr),
                daemon=True,
            )
            client_thread.start()
            self._client_threads.append(client_thread)

            self._client_threads = [
                t for t in self._client_threads if t.is_alive()
            ]

    def _handle_client_thread(self, client_socket, addr):
        """Handle a single client connection in its own thread."""
        try:
            self._handle_client(client_socket)
        except Exception:
            self._log(f"Error handling client {addr}: {traceback.format_exc()}")
        finally:
            # Remove from tracked sockets
            with self._clients_lock:
                try:
                    self._client_sockets.remove(client_socket)
                except ValueError:
                    pass
            try:
                client_socket.close()
            except Exception:
                pass
            self._log(f"Client {addr} disconnected")

    def _handle_client(self, client_socket):
        """Handle a single client connection, processing newline-delimited JSON."""
        client_socket.settimeout(None)  # Blocking reads
        buffer = ""

        while self._running:
            try:
                data = client_socket.recv(65536)
                if not data:
                    break  # Client disconnected

                buffer += data.decode("utf-8")

                # Process all complete lines in the buffer
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    response = self._process_request(line)
                    response_bytes = (json.dumps(response, default=str) + "\n").encode("utf-8")
                    client_socket.sendall(response_bytes)

            except ConnectionResetError:
                break
            except Exception:
                self._log(f"Error in client handler: {traceback.format_exc()}")
                break

    def _process_request(self, raw_json):
        """Parse a JSON request and dispatch to the callback."""
        try:
            request = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}

        if not isinstance(request, dict):
            return {"success": False, "error": "Request must be a JSON object"}

        action = request.get("action")
        if not action:
            return {"success": False, "error": "Missing 'action' field"}

        try:
            result = self._request_callback(request)
            return result
        except Exception:
            tb = traceback.format_exc()
            self._log(f"Handler error for '{action}': {tb}")
            return {"success": False, "error": f"Handler error: {tb}"}
