# Fusion 360 CAM CLI (`fusion-cam`)

> **WARNING — This project is a work in progress.**
>
> 1. **APIs may change without notice.** Commands, behavior, and configuration are still evolving.
> 2. **The optional installer can edit Cursor/Claude `mcp.json`** (`fusion-cam --install` may remove legacy `fusion360-cam-mcp*` entries that pointed at the old bundled server). It does not register a new server entry by default.
> 3. **In full mode, assistants can write data directly to your Fusion 360 document** — including feeds, speeds, and machining parameters. Incorrect changes could affect real toolpaths and G-code output.
> 4. **Windows installation and usage is lightly tested;** report issues if something breaks.

A **Python CLI** that talks to Fusion 360 CAM over a small **TCP JSON** protocol. The **fusion-bridge** add-in runs inside Fusion, listens on `127.0.0.1:9876`, and executes query scripts on the Fusion main thread. The add-in is generic TCP → Fusion API, not CAM-only.

Use it from a terminal, from scripts, or from agent tools that run shell commands (for example Cursor). There are **no GitHub release binaries** and **no PyInstaller build**; install with **pip** from a clone (or a future PyPI package).

## Architecture

```mermaid
flowchart LR
    Terminal -->|"fusion-cam (JSON stdout)"| CLI
    CLI -->|"TCP"| Bridge
    Bridge -->|"adsk.cam API"| Fusion_360
```

- **`fusion-cam`** — this repo, package `fusion_cam` under `src/fusion_cam/`. Stdlib only.
- **`fusion-bridge/`** — Fusion 360 add-in. Any local client can send Python over TCP.

## Commands (overview)

Read commands work in the default **read-only** mode. Writes need **`--mode full`** on the same invocation.

### Read

| Command | Description |
| ------- | ----------- |
| `ping` | Health check — bridge reachable |
| `list-documents` | Open documents and CAM summary |
| `get-document-info` | Active document metadata |
| `get-setups` | Setups, machine, stock, materials |
| `get-operations` | Operations, feeds, speeds, tools, coolant, notes |
| `get-operation-details` | Full parameter dump + computed metrics |
| `get-tools` | Tools in the document |
| `get-library-tools` | External tool libraries |
| `get-machining-time` | Estimated cycle times |
| `get-toolpath-status` | Toolpath validity / outdated |
| `get-nc-programs` | NC programs and post settings |
| `list-material-libraries` | Material libraries |
| `get-material-properties` | Material properties |

### Write (`--mode full`)

| Command | Description |
| ------- | ----------- |
| `update-operation-parameters` | Feeds, speeds, engagement |
| `assign-body-material` | Assign library material to a body |
| `create-custom-material` | Copy material and override properties |
| `update-setup-machine-params` | Machine limits on a setup |
| `generate-toolpaths` | Regenerate toolpaths |
| `post-process` | Post to NC/G-code |

Use `fusion-cam COMMAND --help` for flags and examples. Output is **one JSON object** on stdout: `{"success": true, "data": ...}` or `{"success": false, "error": "...", "code": "..."}`.

## Prerequisites

1. **Fusion 360** — [Autodesk](https://www.autodesk.com/products/fusion-360/overview)
2. **Python 3.10+** on the machine where you run the CLI

## Quick install

From a clone of this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
fusion-cam --install        # copies bridge add-in; optional legacy mcp.json cleanup
```

Or run the helper script (expects you to already be in the repo, or set `FUSION_CAM_CLONE_DIR`):

```bash
bash install.sh
```

**Windows (PowerShell):** `.\install.ps1`

Then in Fusion: **UTILITIES → ADD-INS** → run **fusion-bridge** (optionally **Run on Startup**).

## Manual add-in (contributors)

If you skip `fusion-cam --install`, add the repo folder `fusion-bridge/` via the green **+** next to My Add-Ins so Fusion loads it directly from git.

Upgrading from the old **`fusion-mcp-bridge`** add-in: run **`fusion-cam --install`** again — it installs to **`fusion-bridge`** and removes the previous **`fusion-mcp-bridge`** folder under Fusion’s AddIns when possible. Remove the old add-in from the Fusion UI if it still appears.

## Configuration

### TCP port

Default **`9876`**. Override with **`FUSION_CAM_BRIDGE_PORT`** (or legacy **`FUSION_CAM_MCP_PORT`**) for both the CLI and the add-in.

### Machining time defaults

Same assumptions as before (feed scale, rapid rate, tool-change time); see `get-machining-time` help for details.

## How it works

1. The bridge starts a **localhost-only** TCP server.
2. The CLI loads query modules from `src/fusion_cam/queries/` and sends them to the bridge.
3. The bridge runs them on Fusion’s **main thread** and returns JSON.

Security model: only local processes can connect. Scripts are executed by design; treat the machine as trusted.

## Uninstall

```bash
fusion-cam --uninstall
```

Removes the copied add-in from Fusion’s AddIns folder, metadata under `fusion-cam-cli`, and legacy **`fusion360-cam-mcp*`** entries from Cursor/Claude `mcp.json` when present.

If you previously used **release binaries** installed under `Application Support/fusion-cam-mcp`, remove that folder yourself; the CLI no longer installs a binary there.

## Agents (Cursor)

See `.cursor/rules/fusion-cam-cli.mdc` for how to invoke `fusion-cam` from the terminal and interpret JSON.

## License

[MIT](LICENSE)
