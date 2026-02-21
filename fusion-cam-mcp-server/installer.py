"""
Self-installer for the Fusion 360 CAM MCP server.

When invoked via `--install`, this module:
  1. Copies the binary to a platform-standard location
  2. Extracts the bundled Fusion MCP Bridge add-in to the Fusion 360 AddIns directory
  3. Writes/merges the MCP config for Claude Desktop and/or Cursor
  4. Records the installed version for upgrade tracking

When invoked via `--uninstall`, removes the binary, add-in, and MCP config entries.
"""

import json
import os
import platform
import shutil
import sys
import tempfile


# ── Version ───────────────────────────────────────────────────────────

def _get_version() -> str:
    """Read __version__ from the already-running main module."""
    main = sys.modules.get("__main__")
    return getattr(main, "__version__", "unknown")


# ── Path helpers ──────────────────────────────────────────────────────

def _get_install_dir() -> str:
    """Platform-standard location for the MCP server binary."""
    system = platform.system()
    if system == "Darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support", "fusion-cam-mcp",
        )
    elif system == "Windows":
        return os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")),
            "fusion-cam-mcp",
        )
    return os.path.join(
        os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")),
        "fusion-cam-mcp",
    )


INSTALL_DIR = _get_install_dir()


def _get_fusion_addins_dir() -> str:
    """Standard Fusion 360 AddIns directory where add-ins are auto-discovered."""
    system = platform.system()
    if system == "Darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support", "Autodesk",
            "Autodesk Fusion 360", "API", "AddIns",
        )
    elif system == "Windows":
        return os.path.join(
            os.environ.get("APPDATA", ""),
            "Autodesk", "Autodesk Fusion 360", "API", "AddIns",
        )
    return os.path.join(os.path.expanduser("~"), "fusion-cam-mcp", "fusion-mcp-bridge")


ADDIN_DEST = os.path.join(_get_fusion_addins_dir(), "fusion-mcp-bridge")


def _get_binary_name() -> str:
    if platform.system() == "Windows":
        return "fusion-cam-mcp.exe"
    return "fusion-cam-mcp"


def _get_binary_path() -> str:
    """Resolve the absolute path of the running binary / script."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "server.py"))


def _get_installed_binary_path() -> str:
    """The permanent location for the binary inside INSTALL_DIR."""
    if getattr(sys, "frozen", False):
        return os.path.join(INSTALL_DIR, _get_binary_name())
    return _get_binary_path()


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
    return os.path.join(os.path.expanduser("~"), ".cursor", "mcp.json")


# ── Prompts & validation ─────────────────────────────────────────────

def _prompt(message: str, default: str = "1", valid: set | None = None) -> str:
    """Prompt for input with optional validation. Re-prompts on invalid input."""
    while True:
        try:
            answer = input(f"  {message} [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        result = answer or default
        if valid is None or result in valid:
            return result
        print(f"  Invalid choice '{result}'. Please enter one of: {', '.join(sorted(valid))}")


# ── Pre-flight checks ────────────────────────────────────────────────

def _get_fusion_base_dir() -> str:
    """The Autodesk Fusion 360 data directory (parent of API/AddIns)."""
    system = platform.system()
    if system == "Darwin":
        return os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support", "Autodesk", "Autodesk Fusion 360",
        )
    elif system == "Windows":
        return os.path.join(
            os.environ.get("APPDATA", ""), "Autodesk", "Autodesk Fusion 360",
        )
    return ""


def _check_fusion_installed() -> bool:
    fusion_dir = _get_fusion_base_dir()
    if not fusion_dir:
        return True
    return os.path.isdir(fusion_dir)


def _check_claude_installed() -> bool:
    config_path = _get_claude_config_path()
    return os.path.isdir(os.path.dirname(config_path))


def _check_cursor_installed() -> bool:
    return os.path.isdir(os.path.join(os.path.expanduser("~"), ".cursor"))


# ── Binary relocation ─────────────────────────────────────────────────

def _install_binary() -> str:
    """Copy the binary into INSTALL_DIR so it has a permanent home.
    Returns the installed path. No-op when running from source."""
    if not getattr(sys, "frozen", False):
        return _get_binary_path()

    src = _get_binary_path()
    dest = _get_installed_binary_path()

    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
    except OSError as e:
        print(f"  ERROR: Cannot create install directory: {e}")
        sys.exit(1)

    if os.path.abspath(src) == os.path.abspath(dest):
        return dest

    try:
        if platform.system() == "Windows" and os.path.exists(dest):
            old = dest + ".old"
            try:
                os.replace(dest, old)
            except OSError:
                pass
            shutil.copy2(src, dest)
            try:
                os.remove(old)
            except OSError:
                pass
        else:
            shutil.copy2(src, dest)
            os.chmod(dest, 0o755)
    except (OSError, PermissionError) as e:
        print(f"  ERROR: Cannot install binary to {dest}: {e}")
        sys.exit(1)

    return dest


# ── Add-in extraction ─────────────────────────────────────────────────

def _extract_addin() -> str:
    """Copy the bundled add-in directory to the Fusion AddIns location.
    Returns dest path."""
    source = _get_bundled_addin_dir()
    if not os.path.isdir(source):
        print(f"  ERROR: Add-in source not found at {source}")
        sys.exit(1)

    try:
        shutil.copytree(source, ADDIN_DEST, dirs_exist_ok=True)
    except (OSError, PermissionError) as e:
        print(f"  ERROR: Cannot extract add-in to {ADDIN_DEST}: {e}")
        sys.exit(1)

    return ADDIN_DEST


# ── MCP config writing ───────────────────────────────────────────────

_MCP_SERVER_PREFIX = "fusion360-cam-mcp"


def _build_server_entry(binary_path: str, mode: str) -> dict:
    if getattr(sys, "frozen", False):
        entry = {"command": binary_path, "args": []}
    else:
        python_path = sys.executable
        entry = {"command": python_path, "args": [binary_path]}

    entry["args"].extend(["--mode", "full" if mode == "full" else "read-only"])

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
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
    except OSError as e:
        print(f"  ERROR: Cannot create config directory: {e}")
        return

    existing = {}
    if os.path.isfile(target_path):
        print(f"  Existing {label} config found — merging...")
        backup_path = target_path + ".backup"
        try:
            shutil.copy2(target_path, backup_path)
        except OSError:
            pass

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            print(f"  WARNING: {label} config has invalid JSON.")
            repair = _prompt(f"  Overwrite with fresh config? (y/n)", "n", {"y", "n"})
            if repair.lower() != "y":
                print(f"  Skipping {label} — fix the JSON and re-run the installer.")
                print(f"    Config: {target_path}")
                if os.path.isfile(backup_path):
                    print(f"    Backup: {backup_path}")
                return
            existing = {}
        except OSError as e:
            print(f"  ERROR: Cannot read {label} config: {e}")
            return

    existing.setdefault("mcpServers", {})

    for name, config in servers.items():
        action = "Updating" if name in existing["mcpServers"] else "Adding"
        print(f"    {action}: {name}")
        existing["mcpServers"][name] = config

    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(target_path), suffix=".tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, target_path)
    except OSError as e:
        print(f"  ERROR: Cannot write {label} config: {e}")
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return

    print(f"  Written to {target_path}")


# ── Version tracking ─────────────────────────────────────────────────

def _version_file() -> str:
    return os.path.join(INSTALL_DIR, "version.json")


def _read_installed_version() -> str | None:
    path = _version_file()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version")
    except (json.JSONDecodeError, OSError):
        return None


def _write_installed_version(version: str) -> None:
    path = _version_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"version": version}, f, indent=2)
            f.write("\n")
    except OSError:
        pass


# ── Uninstall ─────────────────────────────────────────────────────────

def _remove_mcp_keys(target_path: str, label: str) -> None:
    """Remove fusion360-cam-mcp* keys from an MCP config file."""
    if not os.path.isfile(target_path):
        return

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"  WARNING: Cannot read {label} config at {target_path}, skipping.")
        return

    mcp_servers = config.get("mcpServers", {})
    keys_to_remove = [k for k in mcp_servers if k.startswith(_MCP_SERVER_PREFIX)]

    if not keys_to_remove:
        print(f"  No fusion360-cam-mcp entries found in {label} config.")
        return

    for key in keys_to_remove:
        del mcp_servers[key]
        print(f"    Removed: {key}")

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        print(f"  Updated {target_path}")
    except OSError as e:
        print(f"  ERROR: Cannot write {label} config: {e}")


def run_uninstall() -> None:
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     Fusion 360 CAM MCP — Uninstall           ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    confirm = _prompt("  This will remove all installed components. Continue? (y/n)", "n", {"y", "n"})
    if confirm.lower() != "y":
        print("  Cancelled.")
        return

    # Remove binary and version file from INSTALL_DIR
    print()
    print("── Removing binary ──")
    binary_path = _get_installed_binary_path()
    removed_binary = False
    if os.path.isfile(binary_path):
        try:
            os.remove(binary_path)
            print(f"  Removed {binary_path}")
            removed_binary = True
        except OSError as e:
            print(f"  ERROR: Cannot remove binary: {e}")
    else:
        print(f"  Binary not found at {binary_path}")

    version_path = _version_file()
    if os.path.isfile(version_path):
        try:
            os.remove(version_path)
        except OSError:
            pass

    # Remove INSTALL_DIR if empty
    if removed_binary and os.path.isdir(INSTALL_DIR):
        try:
            os.rmdir(INSTALL_DIR)
        except OSError:
            pass

    # Remove add-in
    print()
    print("── Removing Fusion MCP Bridge add-in ──")
    if os.path.isdir(ADDIN_DEST):
        try:
            shutil.rmtree(ADDIN_DEST)
            print(f"  Removed {ADDIN_DEST}")
        except OSError as e:
            print(f"  ERROR: Cannot remove add-in: {e}")
    else:
        print(f"  Add-in not found at {ADDIN_DEST}")

    # Remove MCP config entries
    print()
    print("── Removing MCP configuration ──")
    _remove_mcp_keys(_get_claude_config_path(), "Claude Desktop")
    _remove_mcp_keys(_get_cursor_config_path(), "Cursor")

    print()
    print("── Uninstall complete! ──")
    print()
    print("  You can also remove the Fusion add-in from Fusion 360:")
    print('    UTILITIES > ADD-INS > right-click fusion-mcp-bridge > Delete')
    print()


# ── Main install flow ─────────────────────────────────────────────────

def run_install() -> None:
    version = _get_version()

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     Fusion 360 CAM MCP — Install             ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"  Install dir: {INSTALL_DIR}")

    # Version check
    installed = _read_installed_version()
    if installed:
        if installed == version:
            print(f"  Version:     {version} (already installed)")
        else:
            print(f"  Upgrading:   {installed} → {version}")
    else:
        print(f"  Version:     {version}")
    print()

    # ── Mode ──
    print("── Server mode ──")
    print()
    print("  1) Read-only  — safe, inspection and analysis only (recommended)")
    print("  2) Full       — DANGER read + write, can modify feeds/speeds/materials")
    print("  3) Both       — DANGER installs two separate server entries")
    print()
    mode_choice = _prompt("Choice", "1", {"1", "2", "3"})

    # ── Target ──
    print()
    print("── MCP client configuration ──")
    print()
    print("  1) Claude Desktop (free model sonnet 4.6 not recommended)")
    print("  2) Cursor")
    print("  3) Both")
    print("  4) Skip — I'll configure it myself")
    print()
    target_choice = _prompt("Choice", "1", {"1", "2", "3", "4"})

    # ── Install binary ──
    print()
    print("── Installing binary ──")
    binary_path = _install_binary()
    print(f"  Binary installed to: {binary_path}")

    # ── Extract add-in ──
    print()
    print("── Extracting Fusion MCP Bridge add-in ──")
    if not _check_fusion_installed():
        print("  WARNING: Fusion 360 does not appear to be installed.")
        print(f"  Expected directory not found: {_get_fusion_base_dir()}")
        skip = _prompt("  Install add-in anyway? (y/n)", "n", {"y", "n"})
        if skip.lower() != "y":
            print("  Skipping add-in extraction.")
            addin_path = None
        else:
            addin_path = _extract_addin()
            print(f"  Add-in files extracted to: {addin_path}")
    else:
        addin_path = _extract_addin()
        print(f"  Add-in files extracted to: {addin_path}")

    # ── Write MCP config (points to permanent binary location) ──
    if target_choice == "4":
        print()
        print("── Skipping MCP configuration (manual setup) ──")
        print(f"  Binary path: {binary_path}")
        if mode_choice in ("2", "3"):
            print(f"  Full mode args: --mode full")
    else:
        servers = _build_mcp_servers(binary_path, mode_choice)

        print()
        print("── Writing MCP configuration ──")
        if target_choice in ("1", "3"):
            if not _check_claude_installed():
                print("  WARNING: Claude Desktop does not appear to be installed.")
                proceed = _prompt("  Write config anyway? (y/n)", "y", {"y", "n"})
                if proceed.lower() == "y":
                    _merge_config(_get_claude_config_path(), "Claude Desktop", servers)
                else:
                    print("  Skipping Claude Desktop configuration.")
            else:
                _merge_config(_get_claude_config_path(), "Claude Desktop", servers)
        if target_choice in ("2", "3"):
            if not _check_cursor_installed():
                print("  WARNING: Cursor does not appear to be installed.")
                proceed = _prompt("  Write config anyway? (y/n)", "y", {"y", "n"})
                if proceed.lower() == "y":
                    _merge_config(_get_cursor_config_path(), "Cursor", servers)
                else:
                    print("  Skipping Cursor configuration.")
            else:
                _merge_config(_get_cursor_config_path(), "Cursor", servers)

    # ── Write version ──
    _write_installed_version(version)

    # ── Done ──
    apps = {
        "1": "Claude Desktop",
        "2": "Cursor",
        "3": "Claude Desktop and Cursor",
        "4": "your MCP client",
    }.get(target_choice, "Claude Desktop")

    print()
    print("── Setup complete! ──")
    print()
    if addin_path:
        print("  The Fusion MCP Bridge add-in has been installed to:")
        print(f"    {addin_path}")
        print()
        print("  To activate it:")
        print()
        print("    1. Open Fusion 360")
        print('    2. Go to UTILITIES > ADD-INS (or press Shift+S)')
        print('    3. Find "fusion-mcp-bridge" under My Add-Ins and click Run')
        print('    4. (Optional) Check "Run on Startup" for auto-start')
    else:
        print("  The add-in was not installed. Once Fusion 360 is installed,")
        print("  re-run the installer to extract the add-in.")
    print()
    print(f"  Then restart {apps} to pick up the new MCP config.")
    print()
    print("  To uninstall later, run:")
    print(f"    {_get_installed_binary_path()} --uninstall")
    print()
