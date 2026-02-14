# Fusion 360 CAM MCP Server

A read-only MCP server that exposes Fusion 360 CAM/manufacturing data to AI assistants (Cursor, Claude, etc.). Query setups, operations, tools, feeds & speeds, machining times, and toolpath status -- then get AI-powered analysis of your CNC machining parameters.

**This is the first MCP server focused on CAM/manufacturing.**

## Architecture

```
Cursor / Claude  --MCP (stdio)-->  MCP Server (Python)  --TCP-->  Fusion 360 Add-in  --adsk.cam API-->  Fusion 360
```

Two components:

- **MCP Server** (`fusion-cam-mcp-server/`) -- standalone Python process that Cursor launches via stdio. Connects to the add-in over TCP.
- **Fusion 360 Add-in** (`fusion-cam-mcp-addin/`) -- runs inside Fusion 360, listens on `localhost:9876`, executes CAM API queries on the main thread via `CustomEvent`.

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Health check -- verify the add-in connection is alive |
| `get_document_info` | Active document name, units, CAM setup/operation counts |
| `get_setups` | All setups: name, type, stock mode, WCS origin, operation count |
| `get_operations` | Operations in a setup: type, strategy, tool, feeds, speeds, stepover/stepdown |
| `get_operation_details` | Full parameter dump + computed metrics (chip load, surface speed, stepover ratio) |
| `get_tools` | All tools in use: type, diameter, flute count, lengths, which operations use them |
| `get_machining_time` | Estimated cycle time per setup/operation |
| `get_toolpath_status` | Which toolpaths are generated, valid, outdated, or have warnings |

## Setup

### 1. Clone and install Python dependencies

The MCP server needs `mcp` and `pydantic`. The Fusion add-in has zero external dependencies.

**With uv (recommended):**

```bash
git clone <repo-url> fusion-cam-mcp
cd fusion-cam-mcp
uv venv .venv
uv pip install -r requirements.txt
```

**With plain venv:**

```bash
git clone <repo-url> fusion-cam-mcp
cd fusion-cam-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Install the Fusion 360 add-in

**Automatic (macOS/Windows):**

```bash
./install.sh
```

This creates a symlink from Fusion's AddIns directory to the add-in source, so edits are reflected immediately.

**Manual:**

Symlink or copy `fusion-cam-mcp-addin/` into Fusion 360's add-ins directory:

- **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
- **Windows:** `%APPDATA%/Autodesk/Autodesk Fusion 360/API/AddIns/`

### 3. Start the add-in in Fusion 360

1. Open Fusion 360
2. Go to **UTILITIES > ADD-INS** (or press `Shift+S`)
3. In the **Add-Ins** tab, find `fusion-cam-mcp-addin`
4. Click **Run**

The add-in will begin listening on `localhost:9876`.

### 4. Configure Cursor MCP

Add this to your Cursor MCP settings (`.cursor/mcp.json` or global settings):

```json
{
  "mcpServers": {
    "fusion360-cam": {
      "command": "/absolute/path/to/fusion-cam-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/fusion-cam-mcp/fusion-cam-mcp-server/server.py"]
    }
  }
}
```

Replace `/absolute/path/to/fusion-cam-mcp` with the actual path to this repo.

## Usage Examples

Once connected, ask your AI assistant things like:

- "What setups and operations are in my current Fusion document?"
- "Review the feeds and speeds for my adaptive clearing operation"
- "What's the chip load and surface speed for each operation?"
- "Are any toolpaths outdated or need regeneration?"
- "How long will each setup take to machine?"
- "Compare the stepover ratios across my finishing operations"

## Configuration

### TCP Port

The default TCP port is `9876`. Override it by setting the `FUSION_CAM_MCP_PORT` environment variable -- both the add-in and the MCP server read it:

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

## Project Structure

```
fusion-cam-mcp/
  README.md
  requirements.txt               # MCP server dependencies (mcp, pydantic)
  install.sh                     # Symlinks add-in into Fusion's AddIns dir
  .gitignore
  fusion-cam-mcp-server/
    server.py                    # MCP server entry point (FastMCP, stdio)
    fusion_client.py             # TCP client to communicate with add-in
  fusion-cam-mcp-addin/
    fusion-cam-mcp-addin.py      # Add-in entry point (run/stop)
    fusion-cam-mcp-addin.manifest # Fusion add-in manifest
    cam_handler.py               # CAM API query handlers
    tcp_server.py                # TCP listener + JSON framing
```

## How It Works

1. The Fusion 360 add-in starts a TCP server in a background thread
2. When a request arrives, it fires a `CustomEvent` to marshal the call onto Fusion's main thread (required for all `adsk.*` API access)
3. The CAM handler queries Fusion's API (`adsk.cam`) and returns JSON
4. The MCP server receives the JSON over TCP and returns it as an MCP tool result
5. The AI assistant parses the data and provides analysis

## Future Plans

- **Phase 2:** Write operations -- modify feeds/speeds, reorder operations, change tools
- **Phase 3:** Toolpath generation, post-processing integration
- **Phase 4:** Built-in machining knowledge base with material-specific recommendations
