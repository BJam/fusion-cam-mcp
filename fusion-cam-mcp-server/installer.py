"""
Self-installer for the Fusion 360 CAM MCP server.

When invoked via `--install`, this module:
  1. Extracts the bundled Fusion MCP Bridge add-in to ~/fusion-cam-mcp/fusion-mcp-bridge/
  2. Writes/merges the MCP config for Claude Desktop and/or Cursor
  3. Prints instructions for the Fusion 360 add-in setup
"""

import json
import os
import platform
import shutil
import sys


ADDIN_FILES = [
    "fusion-mcp-bridge.py",
    "fusion-mcp-bridge.manifest",
    "tcp_server.py",
    "executor.py",
]

INSTALL_DIR = os.path.join(os.path.expanduser("~"), "fusion-cam-mcp")
ADDIN_DEST = os.path.join(INSTALL_DIR, "fusion-mcp-bridge")


def _get_binary_path() -> str:
    """Resolve the absolute path of the running binary / script."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "server.py"))


def _get_bundled_addin_dir() -> str:
    """Locate the bundled fusion-mcp-bridge directory."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "fusion-mcp-bridge")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "fusion-mcp-bridge")


def _get_claude_config_path() -> str:
    system = platform.system()
    if system == "Darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support", "Claude",
            "claude_desktop_config.json",
        )
    elif system == "Windows":
        return os.path.join(
            os.environ.get("APPDATA", ""),
            "Claude", "claude_desktop_config.json",
        )
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
        "Claude", "claude_desktop_config.json",
    )


def _get_cursor_config_path() -> str:
    return os.path.join(os.getcwd(), ".cursor", "mcp.json")


def _prompt(message: str, default: str = "1") -> str:
    try:
        answer = input(f"  {message} [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return answer or default


# ── Add-in extraction ─────────────────────────────────────────────────

def _extract_addin() -> str:
    """Copy the bundled add-in files to the install directory. Returns dest path."""
    source = _get_bundled_addin_dir()
    if not os.path.isdir(source):
        print(f"  ERROR: Add-in source not found at {source}")
        sys.exit(1)

    os.makedirs(ADDIN_DEST, exist_ok=True)

    for filename in ADDIN_FILES:
        src = os.path.join(source, filename)
        dst = os.path.join(ADDIN_DEST, filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    return ADDIN_DEST


# ── MCP config writing ───────────────────────────────────────────────

def _build_server_entry(binary_path: str, mode: str) -> dict:
    if getattr(sys, "frozen", False):
        entry = {"command": binary_path, "args": []}
    else:
        python_path = sys.executable
        entry = {"command": python_path, "args": [binary_path]}

    if mode == "full":
        entry["args"].extend(["--mode", "full"])

    return entry


def _build_mcp_servers(binary_path: str, mode_choice: str) -> dict:
    servers = {}
    if mode_choice == "2":
        servers["fusion360-cam-mcp"] = _build_server_entry(binary_path, "full")
    elif mode_choice == "3":
        servers["fusion360-cam-mcp-readonly"] = _build_server_entry(binary_path, "readonly")
        servers["fusion360-cam-mcp-full"] = _build_server_entry(binary_path, "full")
    else:
        servers["fusion360-cam-mcp"] = _build_server_entry(binary_path, "readonly")
    return servers


def _merge_config(target_path: str, label: str, servers: dict) -> None:
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    if os.path.isfile(target_path):
        print(f"  Existing {label} config found — merging...")
        with open(target_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {}

    existing.setdefault("mcpServers", {})

    for name, config in servers.items():
        action = "Updating" if name in existing["mcpServers"] else "Adding"
        print(f"    {action}: {name}")
        existing["mcpServers"][name] = config

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
        f.write("\n")

    print(f"  Written to {target_path}")


# ── Main install flow ─────────────────────────────────────────────────

def run_install() -> None:
    binary_path = _get_binary_path()

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     Fusion 360 CAM MCP — Install             ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Binary: {binary_path}")
    print()

    # ── Mode ──
    print("── Server mode ──")
    print()
    print("  1) Read-only  — safe, inspection and analysis only (recommended)")
    print("  2) Full       — read + write, can modify feeds/speeds/materials")
    print("  3) Both       — installs two separate server entries")
    print()
    mode_choice = _prompt("Choice", "1")

    # ── Target ──
    print()
    print("── MCP client configuration ──")
    print()
    print("  1) Claude Desktop  (free, recommended)")
    print("  2) Cursor")
    print("  3) Both")
    print()
    target_choice = _prompt("Choice", "1")

    # ── Extract add-in ──
    print()
    print("── Extracting Fusion MCP Bridge add-in ──")
    addin_path = _extract_addin()
    print(f"  Add-in files extracted to: {addin_path}")

    # ── Write MCP config ──
    servers = _build_mcp_servers(binary_path, mode_choice)

    print()
    print("── Writing MCP configuration ──")
    if target_choice in ("1", "3"):
        _merge_config(_get_claude_config_path(), "Claude Desktop", servers)
    if target_choice in ("2", "3"):
        _merge_config(_get_cursor_config_path(), "Cursor", servers)

    # ── Done ──
    apps = {
        "1": "Claude Desktop",
        "2": "Cursor",
        "3": "Claude Desktop and Cursor",
    }.get(target_choice, "Claude Desktop")

    print()
    print("── Setup complete! ──")
    print()
    print("  One manual step remains — install the Fusion 360 add-in:")
    print()
    print("    1. Open Fusion 360")
    print('    2. Go to UTILITIES > ADD-INS (or press Shift+S)')
    print('    3. In the Add-Ins tab, click the green + next to "My Add-Ins"')
    print("    4. Navigate to:")
    print(f"       {addin_path}")
    print("    5. Select fusion-mcp-bridge and click Run")
    print('    6. (Optional) Check "Run on Startup" for auto-start')
    print()
    print(f"  Then restart {apps} to pick up the new MCP config.")
    print()
