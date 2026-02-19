"""
TCP client for communicating with the Fusion MCP Bridge.

Sends newline-delimited JSON requests over TCP and reads JSON responses.
"""

import json
import os
import socket

DEFAULT_PORT = 9876
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TIMEOUT = 30.0


def get_port():
    """Return the configured TCP port."""
    try:
        return int(os.environ.get("FUSION_CAM_MCP_PORT", DEFAULT_PORT))
    except (ValueError, TypeError):
        return DEFAULT_PORT


class FusionClient:
    """
    TCP client that connects to the Fusion MCP Bridge.
    Maintains a persistent connection for the lifetime of the MCP server.
    """

    def __init__(self, host=None, port=None, timeout=None):
        self._host = host or DEFAULT_HOST
        self._port = port or get_port()
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._socket = None

    def _ensure_connected(self):
        """Connect to the add-in if not already connected."""
        if self._socket is not None:
            return

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._timeout)
            self._socket.connect((self._host, self._port))
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            self._socket = None
            raise ConnectionError(
                f"Cannot connect to Fusion MCP Bridge at "
                f"{self._host}:{self._port}. "
                f"Make sure Fusion 360 is running and the bridge is started. "
                f"Error: {e}"
            )

    def _disconnect(self):
        """Close the connection."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def send_request(self, action, params=None):
        """
        Send a request to the add-in and return the parsed response.

        Args:
            action: The action name (e.g., "get_setups")
            params: Optional dict of parameters

        Returns:
            dict: The response from the add-in

        Raises:
            ConnectionError: If unable to connect to the add-in
        """
        request = {"action": action}
        if params:
            request["params"] = params

        # Try up to 2 times (reconnect once if connection was lost)
        for attempt in range(2):
            try:
                self._ensure_connected()
                request_bytes = (json.dumps(request) + "\n").encode("utf-8")
                self._socket.sendall(request_bytes)

                # Read response (newline-delimited)
                response_data = self._read_response()
                return json.loads(response_data)

            except (ConnectionError, ConnectionResetError, BrokenPipeError, OSError) as e:
                self._disconnect()
                if attempt == 0:
                    continue  # Retry once
                raise ConnectionError(
                    f"Lost connection to Fusion MCP Bridge: {e}"
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON response from add-in: {e}")

    def _read_response(self):
        """Read a newline-delimited JSON response from the socket."""
        buffer = ""
        while True:
            data = self._socket.recv(65536)
            if not data:
                raise ConnectionError("Connection closed by bridge")

            buffer += data.decode("utf-8")
            if "\n" in buffer:
                line, _ = buffer.split("\n", 1)
                return line.strip()

    def close(self):
        """Close the connection."""
        self._disconnect()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
