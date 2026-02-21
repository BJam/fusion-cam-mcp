# Fusion 360 CAM MCP Server

> **WARNING: This project is a work in progress.** APIs, tools, and behavior may change without notice. The installer modifies your MCP configuration files (e.g. `~/.cursor/mcp.json`, `claude_desktop_config.json`) to register this server. In full mode, AI assistants can write data directly to your Fusion 360 document — including feeds, speeds, and machining parameters. Incorrect changes could affect real toolpaths and G-code output. Use at your own risk!

An MCP server that exposes Fusion 360 CAM/manufacturing data to AI assistants (Cursor, Claude, etc.). Query setups, operations, tools, feeds & speeds, machining times, and toolpath status -- then get AI-powered analysis of your CNC machining parameters.

Supports both **read-only** (default) and **full** mode with write capabilities for updating feeds/speeds, assigning materials, and modifying machine parameters.

18 tools covering the full CAM workflow: inspect setups, analyze operations, review feeds & speeds, generate toolpaths, and post-process to G-code.

**This is the first MCP server focused on CAM/manufacturing.**

## Architecture

```mermaid
flowchart LR
    Cursor/Claude -->|"MCP (stdio)"| MCP_Server
    MCP_Server -->|TCP| Fusion_Bridge
    Fusion_Bridge -->|"adsk.cam API"| Fusion_360
```



Two components:

- **MCP Server** (`fusion-cam-mcp-server/`) -- standalone Python process that Cursor launches via stdio. Connects to the add-in over TCP.
- **Fusion MCP Bridge** (`fusion-mcp-bridge/`) -- runs inside Fusion 360, listens on `localhost:9876`, executes Python scripts on the main thread via `CustomEvent`. This is a generic bridge -- not CAM-specific -- and could be reused by other MCP servers targeting any Fusion 360 API.

## Available Tools

### Read Tools


| Tool                      | Description                                                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ping`                    | Health check -- verify the add-in connection is alive                                                                                                                             |
| `list_documents`          | List all open Fusion 360 documents with CAM summary info                                                                                                                          |
| `get_document_info`       | Active document name, units, CAM setup/operation counts                                                                                                                           |
| `get_setups`              | All setups: name, type, machine info, stock dimensions, body materials                                                                                                            |
| `get_operations`          | Operations with type, strategy, tool info, feeds, speeds, coolant, notes, stepover/stepdown                                                                                       |
| `get_operation_details`   | Full parameter dump organized by category (feeds, speeds, engagement, linking, drilling, passes, heights, strategy) + computed metrics (chip load, surface speed, stepover ratio) |
| `get_tools`               | All tools in use: type, diameter, flute count, lengths, holder info, which operations use them                                                                                    |
| `get_machining_time`      | Estimated cycle time per setup/operation                                                                                                                                          |
| `get_toolpath_status`     | Which toolpaths are generated, valid, outdated, or have warnings                                                                                                                  |
| `get_nc_programs`         | List all NC programs with their operations, post-processor config, and output settings                                                                                            |
| `list_material_libraries` | Browse available material libraries and their materials                                                                                                                           |
| `get_material_properties` | Read all physical/mechanical properties of a specific material                                                                                                                    |
| `generate_toolpaths`      | Trigger toolpath generation for specific operations or entire setups                                                                                                              |
| `post_process`            | Post-process a setup to generate NC/G-code files using the configured post processor                                                                                              |


### Write Tools (requires `--mode full`) - USE AT YOUR OWN RISK


| Tool                          | Description                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------ |
| `update_operation_parameters` | Update feeds, speeds, and engagement parameters on a CAM operation             |
| `assign_body_material`        | Assign a physical material from a library to a body                            |
| `create_custom_material`      | Create a new material by copying an existing one and overriding properties     |
| `update_setup_machine_params` | Update machine-level parameters on a setup (spindle limits, feed limits, etc.) |


All write tools return a before/after diff showing exactly what changed.

## Prerequisites

You need two things installed before setting up the MCP server:

1. **Fusion 360** -- [Download from Autodesk](https://www.autodesk.com/products/fusion-360/overview)
2. **An MCP client** -- [Claude Desktop](https://claude.ai/download) (free) or [Cursor](https://cursor.com)

No Python installation required -- the MCP server ships as a standalone binary.

## Setup

### 1. Run the install script

The install script downloads the correct binary for your platform, configures Claude Desktop (or Cursor), and extracts the Fusion 360 add-in -- all in one step.

**macOS (Terminal):**

```bash
curl -fsSL https://raw.githubusercontent.com/BJam/fusion-cam-mcp/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/BJam/fusion-cam-mcp/main/install.ps1 | iex
```

The script will prompt you to choose:

- **Mode**: read-only (recommended), full (write), or both
- **Target**: Claude Desktop (recommended), Cursor, or both

Existing MCP configs are merged -- the script won't overwrite your other servers.

> **macOS Gatekeeper note:** Since the binary is not code-signed, macOS may block it on first run. Go to **System Settings > Privacy & Security**, scroll to the bottom, and click **Allow Anyway** next to the blocked binary. The install script runs `xattr -d com.apple.quarantine` to prevent this, but some macOS versions still require manual approval.

> **Windows SmartScreen note:** Windows may show a "Windows protected your PC" warning for the unsigned binary. Click **More info** then **Run anyway** to proceed.

> **Windows execution policy note:** If `irm | iex` is blocked, run this first: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 2. Run the Fusion MCP Bridge add-in

The installer places the add-in in Fusion 360's standard AddIns directory, so it's auto-discovered.

1. Open Fusion 360
2. Go to **UTILITIES > ADD-INS** (or press `Shift+S`)
3. Find **fusion-mcp-bridge** under **My Add-Ins** and click **Run**
4. (Optional) Check **Run on Startup** so it starts automatically with Fusion

The bridge will begin listening on `localhost:9876`.

### 3. Restart your MCP client

Close and reopen Claude Desktop and/or Cursor so it picks up the new MCP configuration. In Claude Desktop, you should see the MCP running in Settings -> Developer -> Local MCP servers. In Cursor, the MCP server will appear in your MCP settings.

### Alternative: Manual / Developer Setup

For contributors or if you prefer to run from source.

#### Clone and install Python dependencies

Requires Python 3.10+. The Fusion add-in has zero external dependencies.

```bash
git clone https://github.com/BJam/fusion-cam-mcp.git
cd fusion-cam-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt    # macOS/Linux
# .venv\Scripts\pip install -r requirements.txt  # Windows
```

#### Install the Fusion MCP Bridge add-in

When running from source, the add-in lives in the repo's `fusion-mcp-bridge/` directory. You need to point Fusion 360 to it manually:

1. Open Fusion 360
2. Go to **UTILITIES > ADD-INS** (or press `Shift+S`)
3. In the **Add-Ins** tab, click the green **+** button next to "My Add-Ins"
4. Navigate to the `fusion-mcp-bridge` folder inside your cloned repo and click **Open**
5. Select **fusion-mcp-bridge** in the list and click **Run**
6. (Optional) Check **Run on Startup** so it starts automatically with Fusion

Unlike the binary installer (which copies the add-in into Fusion's standard AddIns directory for auto-discovery), the dev setup points Fusion directly at the repo directory. This means changes to the bridge code take effect immediately on restart.

#### Configure Claude Desktop

Add the following to your Claude Desktop config file, replacing the paths with the actual location of this repo:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fusion360-cam-mcp": {
      "command": "/absolute/path/to/fusion-cam-mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/fusion-cam-mcp/fusion-cam-mcp-server/server.py"
      ]
    }
  }
}
```

To enable write operations, add `"--mode", "full"` to the args array.

Or run the self-installer from source to auto-configure:

```bash
.venv/bin/python fusion-cam-mcp-server/server.py --install
```

#### Configure Cursor (optional)

Add the same `mcpServers` block to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` in the project root.

## Usage Examples

Once connected, ask your AI assistant things like:

- "What setups and operations are in my current Fusion document?"
- "Review the feeds and speeds for my adaptive clearing operation"
- "What's the chip load and surface speed for each operation?"
- "Are any toolpaths outdated or need regeneration?"
- "How long will each setup take to machine?"
- "Compare the stepover ratios across my finishing operations"
- "What material is assigned to the body in Setup 1?"
- "What coolant mode is set on each operation?"
- "Show me the linking parameters for my contour operation"
- "Change the spindle speed on my finishing pass to 18000 rpm"
- "Assign Aluminum 6061 to the part body"
- "Regenerate toolpaths for all operations in Setup 1"
- "Post-process Setup 1 and output the G-code to my desktop"

## Configuration

### TCP Port

The default TCP port is `9876`. Override it by setting the `FUSION_CAM_MCP_PORT` environment variable -- both the bridge and the MCP server read it:

```json
{
  "mcpServers": {
    "fusion360-cam": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/fusion-cam-mcp-server/server.py"],
      "env": {
        "FUSION_CAM_MCP_PORT": "9877"
      }
    }
  }
}
```

### Machining Time Estimates

The `get_machining_time` tool uses these default assumptions when estimating cycle times:


| Parameter        | Default               | Notes                               |
| ---------------- | --------------------- | ----------------------------------- |
| Feed scale       | 1.0                   | Multiplier on programmed feed rates |
| Rapid feed       | 500 cm/min (~200 IPM) | Machine rapid traverse rate         |
| Tool change time | 15 seconds            | Time per tool change                |


These are reasonable defaults for many machines. Your actual cycle times will vary based on your machine's rapid rates and tool changer speed.

## How It Works

1. The Fusion MCP Bridge starts a TCP server in a background thread, bound to `localhost` only
2. The MCP server loads query scripts from the `queries/` directory and sends them over TCP
3. When a request arrives, the bridge fires a `CustomEvent` to marshal the call onto Fusion's main thread (required for all `adsk.*` API access)
4. The executor runs the query script via `exec()` with the Fusion SDK available in the namespace
5. The result is serialized as JSON and sent back over TCP to the MCP server
6. The AI assistant parses the data and provides analysis

This architecture means all business logic lives in the `queries/` directory on the MCP server side. Iterating on query logic only requires restarting the MCP server -- no Fusion MCP Bridge restart needed.

### Security Note

The bridge's executor runs Python scripts sent over TCP. This is by design -- it allows the MCP server to send query logic without requiring a bridge restart. The TCP server is bound to `127.0.0.1` (localhost only), so only local processes can connect. No remote access is possible.

## Uninstalling

Run the built-in uninstaller to cleanly remove all components:

**macOS:**

```bash
~/Library/Application\ Support/fusion-cam-mcp/fusion-cam-mcp --uninstall
```

**Windows (PowerShell):**

```powershell
& "$env:LOCALAPPDATA\fusion-cam-mcp\fusion-cam-mcp.exe" --uninstall
```

This removes the server binary, the Fusion MCP Bridge add-in files, and the `fusion360-cam-mcp` entries from your Claude Desktop and Cursor configs (other MCP servers are not affected).

To also remove the add-in from Fusion 360's UI, open **UTILITIES > ADD-INS**, right-click **fusion-mcp-bridge**, and select **Delete**.

## License

[MIT](LICENSE)