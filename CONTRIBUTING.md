# Contributing to Fusion 360 CAM MCP Server

Thanks for your interest in contributing! This project aims to bridge AI assistants with Fusion 360's manufacturing/CAM capabilities through the Model Context Protocol.

## Architecture Overview

Before contributing, it helps to understand the two-component architecture:

```
Cursor / Claude  --MCP (stdio)-->  MCP Server (Python)  --TCP-->  Fusion 360 Add-in  --adsk.cam API-->  Fusion 360
```

- **MCP Server** (`fusion-cam-mcp-server/`) -- standalone Python process. All query logic lives in `queries/` as Python scripts.
- **Fusion MCP Bridge** (`fusion-mcp-bridge/`) -- runs inside Fusion 360. This is a generic bridge (not CAM-specific) that executes Python scripts sent over TCP.

The key insight: query scripts in `queries/` are sent to the bridge for execution inside Fusion 360. This means you can iterate on query logic by restarting the MCP server alone -- no Fusion restart needed.

## Development Setup

1. Clone the repo and install dependencies:

```bash
git clone https://github.com/bjam/fusion-cam-mcp.git
cd fusion-cam-mcp
uv venv .venv
uv pip install -r requirements.txt
```

2. Install the Fusion MCP Bridge add-in (see README.md for instructions)

3. Configure Cursor MCP settings to point at the server

## How to Add a New Read Tool

Most contributions will be adding new query tools. Here's the pattern:

### 1. Create the query script

Add a new file in `fusion-cam-mcp-server/queries/`, e.g. `get_something.py`:

```python
# Params: document_name (optional), other_param (required)
# Result: dict with your data

document_name = params.get("document_name")
cam, err = _get_cam(document_name)
if err:
    result = err
else:
    # Your Fusion 360 API logic here
    # All helpers from _helpers.py are available
    result = {"your_data": "here"}
```

The `_helpers.py` file is automatically prepended, giving you access to:
- `_get_cam()`, `_get_document()` -- get Fusion objects
- `_find_setup_by_name()`, `_find_operation_by_name()` -- lookups
- `_read_param()`, `_safe_param_value()` -- parameter reading
- All parameter name constants (`FEED_PARAMS`, `TOOL_GEOM_PARAMS`, etc.)

### 2. Register the MCP tool

Add a tool function in `fusion-cam-mcp-server/server.py`:

```python
@mcp.tool()
def get_something(
    other_param: str,
    document_name: Optional[str] = None,
) -> str:
    """
    Docstring becomes the tool description visible to the AI.
    Be specific about what data is returned and when to use this tool.
    """
    params = {"other_param": other_param}
    if document_name:
        params["document_name"] = document_name

    response = _execute_query("get_something", params)
    if not response.get("success"):
        raise RuntimeError(response.get("error", "Failed"))
    return _format_response(response)
```

### 3. Test it

1. Restart the MCP server (the bridge stays running)
2. Ask the AI to call your new tool
3. Verify the output

## How to Add a New Write Tool

Write tools follow the same pattern but with two additions:

1. Call `_require_write_mode()` at the top to enforce `--mode full`
2. Use `_capture_param_snapshot()` + `_build_diff()` to return before/after diffs

See `update_operation_params.py` for the canonical example.

## Adding New Parameter Categories

If you find Fusion 360 CAM parameters that should be explicitly categorized:

1. Add the parameter mapping dict in `_helpers.py` (follow the existing pattern)
2. Add it to `ALL_PARAM_CATEGORIES` so `get_operation_details` picks it up automatically
3. Parameters not in any category still appear in the "other" bucket

## Code Style

- Keep query scripts focused -- one script per tool
- Use `try/except` around Fusion API calls (they can throw for many reasons)
- Return structured dicts, not formatted strings
- Prefer `_read_param()` over direct parameter access for safety
- No external dependencies in the bridge (it runs inside Fusion's Python environment)

## Pull Requests

1. Fork the repo and create a feature branch
2. Keep changes focused -- one feature or fix per PR
3. Update the README tool table if adding new tools
4. Add a CHANGELOG entry under `[Unreleased]`
5. Test with an actual Fusion 360 document if possible

## Reporting Issues

When reporting bugs, please include:
- Fusion 360 version
- Operating system
- MCP server mode (read-only or full)
- The tool call that failed
- Error message or unexpected output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
