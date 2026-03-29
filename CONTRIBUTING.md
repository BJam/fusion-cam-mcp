# Contributing to Fusion 360 CAM CLI

Thanks for your interest in contributing. This project connects assistants and scripts to Fusion 360 CAM through a **terminal CLI** and the **fusion-bridge** add-in (TCP bridge inside Fusion).

## Architecture

```
Terminal  --fusion-cam-->  Python CLI (fusion_cam)  --TCP-->  Bridge add-in  --adsk.cam-->  Fusion 360
```

- **Package** — `src/fusion_cam/`: `cli.py`, `cam_api.py`, `fusion_client.py`, `queries/`, `installer.py`, `debug_scripts/`.
- **Bridge** — `fusion-bridge/`: runs inside Fusion. Generic TCP executor, not CAM-specific.

Query logic lives in `src/fusion_cam/queries/`. Iterating on queries usually means **re-running the CLI**; the bridge can stay up.

## Development setup

```bash
git clone https://github.com/bjam/fusion-cam-mcp.git
cd fusion-cam-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
fusion-cam --install   # or add fusion-bridge/ manually in Fusion
```

The project is **stdlib-only**; `requirements.txt` only documents that. Builds use **Hatchling** (`pyproject.toml`). Release wheels bundle the add-in via `hatch_build.py` (standard builds only); editable installs use the repo’s `fusion-bridge/` for `--install`.

## Adding a read command

### 1. Query module

Add `src/fusion_cam/queries/my_query.py` with a `run(params)` function (or assign a result as in existing queries). Helpers come from the shared query layer (`_1_base`, etc.); follow neighboring files.

### 2. CLI wiring

Register a subcommand in `src/fusion_cam/cli.py`: handler that builds `params` and calls `session.run_query("my_query", params)` (see existing `_h_*` functions).

### 3. Package exports

If queries are discovered by name from the package, ensure the module is importable (same patterns as existing `queries/*.py`).

## Adding a write command

- Query must enforce safety consistent with other writes (e.g. edit-dialog checks in the bridge executor).
- CLI must document **`--mode full`** in the subcommand help and pass mode through `CamSession` like other write handlers.

## Style

- One focused query module per operation family.
- Return JSON-friendly dicts from bridge-side code.
- Prefer existing helpers over duplicating Fusion API access.
- No extra runtime dependencies in the bridge (Fusion’s Python).

## Pull requests

1. Fork and branch.
2. Keep changes scoped.
3. Update **README** command tables if you add user-facing commands.
4. Add a **CHANGELOG** entry under `[Unreleased]`.
5. Test against a real Fusion document when possible.

## Issues

Include Fusion version, OS, `fusion-cam …` command, and the JSON error payload if any.

## License

Contributions are under the [MIT License](LICENSE).
