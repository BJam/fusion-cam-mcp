"""
fusion-cam — CLI for Fusion 360 CAM (TCP to the fusion-bridge add-in).

Prints one JSON object per invocation on stdout for agent and script use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

from .cam_api import CamSession
from .queries import get_helpers_code
from .version_info import __version__ as _PKG_VER


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _json_type_dict(raw: str) -> dict[str, Any]:
    v = json.loads(raw)
    if not isinstance(v, dict):
        raise argparse.ArgumentTypeError("JSON must be an object {}")
    return v


def _json_type_list(raw: str) -> list[Any]:
    v = json.loads(raw)
    if not isinstance(v, list):
        raise argparse.ArgumentTypeError("JSON must be an array []")
    return v


def _emit(obj: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def _exit_for_result(obj: dict[str, Any]) -> int:
    return 0 if obj.get("success") else 1


# ---------------------------------------------------------------------------
# Global parser
# ---------------------------------------------------------------------------

GLOBAL_EPILOG = """
Environment (optional):
  FUSION_CAM_BRIDGE_PORT   TCP port for the fusion-bridge add-in (default 9876).
  FUSION_CAM_MCP_PORT      Same as above (legacy name; still honored).
  FUSION_CAM_MODE          Default for --mode: read-only | full

Global flags (--mode, --port, --pretty) work before OR after the subcommand, e.g.:
  fusion-cam ping --pretty
  fusion-cam --pretty ping

Getting `fusion-cam` on your PATH:
  From repo root: pip install -e .  (or uv pip install -e .) — installs the
  console script from pyproject.toml.
  From a git checkout: pip install -e .  then  fusion-cam …
  Module: python -m fusion_cam.cli …

Agent workflow (Cursor / coding agents):
  1. Ensure Fusion 360 is running with the fusion-bridge add-in started.
  2. Run `fusion-cam ping --pretty` to verify connectivity.
  3. Use read-only commands to inspect; add `--mode full` for write commands.
  4. Parse stdout as a single JSON object. Field `success` is boolean.
     On failure, `error` (string) and optional `code` (e.g. READ_ONLY,
     CONNECTION_ERROR) are set.
  5. For ad-hoc API exploration, use `fusion-cam debug` (see `fusion-cam debug -h`).

Examples:
  fusion-cam ping --pretty
  fusion-cam get-setups
  fusion-cam get-operations --setup-name "Setup1"
  fusion-cam update-operation-parameters --mode full \\
    --operation-name "2D Adaptive1" \\
    --parameters-json '{"tool_feedCutting":"800 mm/min","tool_spindleSpeed":"10000 rpm"}'
"""


def _apply_globals(ns: argparse.Namespace) -> str:
    if ns.port is not None:
        p = str(ns.port)
        os.environ["FUSION_CAM_BRIDGE_PORT"] = p
        os.environ["FUSION_CAM_MCP_PORT"] = p  # legacy alias for the add-in + older docs
    mode = ns.mode or os.environ.get("FUSION_CAM_MODE", "read-only")
    if mode not in ("read-only", "full"):
        mode = "read-only"
    return mode


# ---------------------------------------------------------------------------
# Handlers: (session, args) -> dict
# ---------------------------------------------------------------------------


def _h_ping(s: CamSession, _: argparse.Namespace) -> dict[str, Any]:
    return s.ping()


def _h_list_documents(s: CamSession, _: argparse.Namespace) -> dict[str, Any]:
    return s.query("list_documents")


def _h_get_document_info(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_document_info", _params(a, ("document_name",)))


def _h_get_setups(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_setups", _params(a, ("document_name",)))


def _h_get_operations(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_operations", _params(a, ("setup_name", "document_name")))


def _h_get_operation_details(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query(
        "get_operation_details",
        _params(a, ("operation_name", "setup_name", "document_name")),
    )


def _h_get_tools(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_tools", _params(a, ("document_name",)))


def _h_get_library_tools(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(a, ("library_name", "tool_type", "min_diameter", "max_diameter"))
    loc = a.location or "local"
    d["location"] = loc
    return s.query("get_library_tools", d)


def _h_get_machining_time(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_machining_time", _params(a, ("setup_name", "document_name")))


def _h_get_toolpath_status(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_toolpath_status", _params(a, ("setup_name", "document_name")))


def _h_get_nc_programs(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("get_nc_programs", _params(a, ("document_name",)))


def _h_generate_toolpaths(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(a, ("setup_name", "document_name"))
    if a.operation_names_json is not None:
        d["operation_names"] = a.operation_names_json
    return s.query("generate_toolpaths", d)


def _h_post_process(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(
        a,
        (
            "setup_name",
            "output_folder",
            "program_name",
            "program_number",
            "document_name",
        ),
    )
    if a.operation_names_json is not None:
        d["operation_names"] = a.operation_names_json
    return s.query("post_process", d)


def _h_update_operation_parameters(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(a, ("operation_name", "setup_name", "document_name"))
    d["parameters"] = a.parameters_json
    return s.query("update_operation_params", d, write=True)


def _h_list_material_libraries(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query("list_material_libraries", _params(a, ("library_name", "document_name")))


def _h_get_material_properties(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query(
        "get_material_properties",
        _params(a, ("material_name", "library_name", "document_name")),
    )


def _h_create_custom_material(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(
        a,
        (
            "new_material_name",
            "source_material_name",
            "source_library_name",
            "document_name",
        ),
    )
    d["property_overrides"] = a.property_overrides_json or {}
    if a.assign_to_bodies_json is not None:
        d["assign_to_bodies"] = a.assign_to_bodies_json
    return s.query("create_custom_material", d, write=True)


def _h_assign_body_material(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    return s.query(
        "assign_body_material",
        _params(
            a,
            ("body_name", "material_name", "library_name", "setup_name", "document_name"),
        ),
        write=True,
    )


def _h_update_setup_machine_params(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    d = _params(a, ("setup_name", "document_name"))
    d["parameters"] = a.parameters_json
    return s.query("update_setup_machine_params", d, write=True)


def _h_debug(s: CamSession, a: argparse.Namespace) -> dict[str, Any]:
    try:
        code = _read_debug_source(a)
    except ValueError as e:
        return {"success": False, "error": str(e), "code": "INVALID_ARGS"}
    params = a.params_json or {}
    helpers = get_helpers_code() if a.with_helpers else None
    return s.debug(code, params, prepend_helpers=a.with_helpers, helpers_source=helpers)


def _h_version(_s: CamSession | None, _a: argparse.Namespace) -> dict[str, Any]:
    return {
        "success": True,
        "data": {"cli": "fusion-cam", "package_version": _PKG_VER},
    }


def _params(a: argparse.Namespace, keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: getattr(a, k) for k in keys if getattr(a, k, None) is not None}


def _read_debug_source(a: argparse.Namespace) -> str:
    if a.code_file:
        with open(a.code_file, encoding="utf-8") as f:
            return f.read()
    if a.code is not None:
        return a.code
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if not raw.strip():
            raise ValueError(
                "debug: stdin was empty; use --code, --file, or pipe Python source"
            )
        return raw
    raise ValueError(
        "debug: provide --code, --file, or pipe Python source on stdin"
    )


# ---------------------------------------------------------------------------
# Build CLI
# ---------------------------------------------------------------------------


def _add_common_doc(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--document-name",
        default=None,
        help="Target open document by name (default: active document).",
    )


def _global_options_parent() -> argparse.ArgumentParser:
    """Shared --mode / --port / --pretty on root and every subparser (either order)."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument(
        "--mode",
        choices=["read-only", "full"],
        default=None,
        help="read-only: no write subcommands. full: enable writes (default: env or read-only).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=None,
        help="fusion-bridge TCP port (overrides FUSION_CAM_BRIDGE_PORT / FUSION_CAM_MCP_PORT).",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (indentation); omit for compact one-line output.",
    )
    return p


def build_parser() -> argparse.ArgumentParser:
    common = _global_options_parent()
    parser = argparse.ArgumentParser(
        prog="fusion-cam",
        parents=[common],
        description=(
            "Fusion 360 CAM bridge CLI — setups, operations, tools, materials, "
            "post-processing, and debug. Writes one JSON object to stdout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=GLOBAL_EPILOG,
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    def subcmd(
        name: str,
        *,
        help_text: str,
        desc: str,
        epilog: str,
        handler: Callable[[CamSession, argparse.Namespace], dict[str, Any]],
    ) -> argparse.ArgumentParser:
        sp = sub.add_parser(
            name,
            parents=[common],
            help=help_text,
            description=desc,
            epilog=epilog,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        sp.set_defaults(_handler=handler)
        return sp

    subcmd(
        "ping",
        help_text="Health check: bridge reachable",
        desc="Verify Fusion 360 is running and the bridge add-in is listening.",
        epilog="Example:\n  fusion-cam ping\n  fusion-cam ping --pretty\n  fusion-cam --pretty ping",
        handler=_h_ping,
    )

    subcmd(
        "list-documents",
        help_text="List open documents and CAM summary",
        desc="Bridge query list_documents.",
        epilog="Example:\n  fusion-cam list-documents --pretty",
        handler=_h_list_documents,
    )

    p = subcmd(
        "get-document-info",
        help_text="Active document name, units, CAM counts",
        desc="Bridge query get_document_info.",
        epilog="Example:\n  fusion-cam get-document-info\n  fusion-cam get-document-info --document-name \"MyPart\"",
        handler=_h_get_document_info,
    )
    _add_common_doc(p)

    p = subcmd(
        "get-setups",
        help_text="List CAM setups",
        desc="Bridge query get_setups.",
        epilog="Example:\n  fusion-cam get-setups --pretty",
        handler=_h_get_setups,
    )
    _add_common_doc(p)

    p = subcmd(
        "get-operations",
        help_text="List operations (feeds, tools, …)",
        desc="Bridge query get_operations.",
        epilog="Example:\n  fusion-cam get-operations\n  fusion-cam get-operations --setup-name \"Setup1\"",
        handler=_h_get_operations,
    )
    p.add_argument("--setup-name", default=None, help="Filter by setup name.")
    _add_common_doc(p)

    p = subcmd(
        "get-operation-details",
        help_text="Full parameter dump for one operation",
        desc="Bridge query get_operation_details.",
        epilog=(
            "Example:\n"
            "  fusion-cam get-operation-details --operation-name \"2D Adaptive1\"\n"
            "  fusion-cam get-operation-details --operation-name \"Facing\" --setup-name \"Setup1\""
        ),
        handler=_h_get_operation_details,
    )
    p.add_argument("--operation-name", required=True, help="Exact operation name.")
    p.add_argument("--setup-name", default=None, help="Narrow search by setup.")
    _add_common_doc(p)

    p = subcmd(
        "get-tools",
        help_text="Document tool library",
        desc="Bridge query get_tools.",
        epilog="Example:\n  fusion-cam get-tools --pretty",
        handler=_h_get_tools,
    )
    _add_common_doc(p)

    p = subcmd(
        "get-library-tools",
        help_text="Browse external tool libraries",
        desc="Bridge query get_library_tools.",
        epilog=(
            "Example:\n"
            '  fusion-cam get-library-tools --location local --tool-type "flat end mill"\n'
            "  fusion-cam get-library-tools --min-diameter 0.6 --max-diameter 2.0"
        ),
        handler=_h_get_library_tools,
    )
    p.add_argument(
        "--location",
        choices=["local", "fusion360", "cloud", "hub"],
        default=None,
        help="Library root (default: local).",
    )
    p.add_argument("--library-name", default=None, help="Substring filter on library file name.")
    p.add_argument("--tool-type", default=None, help="Substring filter on tool type.")
    p.add_argument("--min-diameter", type=float, default=None, help="Min diameter (cm).")
    p.add_argument("--max-diameter", type=float, default=None, help="Max diameter (cm).")

    p = subcmd(
        "get-machining-time",
        help_text="Estimated cycle times",
        desc="Bridge query get_machining_time.",
        epilog="Example:\n  fusion-cam get-machining-time --setup-name \"Setup1\"",
        handler=_h_get_machining_time,
    )
    p.add_argument("--setup-name", default=None, help="Limit to one setup.")
    _add_common_doc(p)

    p = subcmd(
        "get-toolpath-status",
        help_text="Toolpath valid / outdated / suppressed",
        desc="Bridge query get_toolpath_status.",
        epilog="Example:\n  fusion-cam get-toolpath-status --pretty",
        handler=_h_get_toolpath_status,
    )
    p.add_argument("--setup-name", default=None, help="Limit to one setup.")
    _add_common_doc(p)

    p = subcmd(
        "get-nc-programs",
        help_text="NC programs and post settings",
        desc="Bridge query get_nc_programs.",
        epilog="Example:\n  fusion-cam get-nc-programs",
        handler=_h_get_nc_programs,
    )
    _add_common_doc(p)

    p = subcmd(
        "generate-toolpaths",
        help_text="Regenerate toolpaths (long-running)",
        desc="Bridge query generate_toolpaths.",
        epilog=(
            "Example:\n"
            "  fusion-cam generate-toolpaths --mode full --setup-name \"Setup1\"\n"
            '  fusion-cam generate-toolpaths --operation-names-json \'["Op1","Op2"]\''
        ),
        handler=_h_generate_toolpaths,
    )
    p.add_argument("--setup-name", default=None, help="All operations in setup.")
    p.add_argument(
        "--operation-names-json",
        type=_json_type_list,
        default=None,
        help='JSON array of operation names, e.g. \'["Rough","Finish"]\'.',
    )
    _add_common_doc(p)

    p = subcmd(
        "post-process",
        help_text="Post-process setup to NC files",
        desc="Bridge query post_process.",
        epilog=(
            "Example:\n"
            "  fusion-cam post-process --setup-name \"Setup1\" --output-folder /tmp/nc\n"
            "  fusion-cam post-process --setup-name \"Setup1\" --output-folder /tmp/nc "
            "--program-number 1002"
        ),
        handler=_h_post_process,
    )
    p.add_argument("--setup-name", required=True, help="Setup name from get-setups.")
    p.add_argument(
        "--output-folder",
        required=True,
        help="Absolute path to folder for NC output.",
    )
    p.add_argument("--program-name", default=None, help="NC program name (default: setup name).")
    p.add_argument("--program-number", type=int, default=None, help="O-number (default: 1001).")
    p.add_argument(
        "--operation-names-json",
        type=_json_type_list,
        default=None,
        help="JSON array of operation names to include.",
    )
    _add_common_doc(p)

    p = subcmd(
        "update-operation-parameters",
        help_text="Update feeds/speeds/engagement (requires --mode full)",
        desc="Bridge query update_operation_parameters.",
        epilog=(
            "Example:\n"
            "  fusion-cam --mode full update-operation-parameters \\\n"
            '    --operation-name \"2D Adaptive1\" \\\n'
            '    --parameters-json \'{"tool_feedCutting":"750 mm/min","tool_spindleSpeed":"12000 rpm"}\''
        ),
        handler=_h_update_operation_parameters,
    )
    p.add_argument("--operation-name", required=True, help="Operation name.")
    p.add_argument(
        "--parameters-json",
        type=_json_type_dict,
        required=True,
        help='JSON object: CAM param name -> Fusion expression string.',
    )
    p.add_argument("--setup-name", default=None, help="Narrow search by setup.")
    _add_common_doc(p)

    p = subcmd(
        "list-material-libraries",
        help_text="Physical material libraries",
        desc="Bridge query list_material_libraries.",
        epilog="Example:\n  fusion-cam list-material-libraries\n  fusion-cam list-material-libraries --library-name \"Steel\"",
        handler=_h_list_material_libraries,
    )
    p.add_argument("--library-name", default=None, help="List materials in this library only.")
    _add_common_doc(p)

    p = subcmd(
        "get-material-properties",
        help_text="Read one material's properties",
        desc="Bridge query get_material_properties.",
        epilog=(
            "Example:\n"
            '  fusion-cam get-material-properties --material-name "Aluminum 6061" \\\n'
            '    --library-name "Aluminum"'
        ),
        handler=_h_get_material_properties,
    )
    p.add_argument("--material-name", required=True, help="Material name.")
    p.add_argument("--library-name", required=True, help="Library name.")
    _add_common_doc(p)

    p = subcmd(
        "create-custom-material",
        help_text="Copy material + overrides (requires --mode full)",
        desc="Bridge query create_custom_material.",
        epilog=(
            "Example:\n"
            "  fusion-cam --mode full create-custom-material \\\n"
            '    --new-material-name "Custom AL" \\\n'
            '    --source-material-name "Aluminum 6061" \\\n'
            '    --source-library-name "Aluminum" \\\n'
            '    --property-overrides-json \'{"structural_Density":2700}\' \\\n'
            '    --assign-to-bodies-json \'["Body1"]\''
        ),
        handler=_h_create_custom_material,
    )
    p.add_argument("--new-material-name", required=True, help="Name for new material.")
    p.add_argument("--source-material-name", required=True, help="Material to copy.")
    p.add_argument("--source-library-name", required=True, help="Library of source material.")
    p.add_argument(
        "--property-overrides-json",
        type=_json_type_dict,
        default=None,
        help='JSON object of property overrides (default: {}).',
    )
    p.add_argument(
        "--assign-to-bodies-json",
        type=_json_type_list,
        default=None,
        help='Optional JSON array of body names to assign.',
    )
    _add_common_doc(p)

    p = subcmd(
        "assign-body-material",
        help_text="Assign physical material to body (requires --mode full)",
        desc="Bridge query assign_body_material.",
        epilog=(
            "Example:\n"
            "  fusion-cam --mode full assign-body-material \\\n"
            '    --body-name "Body1" --material-name "Aluminum 6061" --library-name "Aluminum"'
        ),
        handler=_h_assign_body_material,
    )
    p.add_argument("--body-name", required=True, help="Body name from get-setups.")
    p.add_argument("--material-name", required=True, help="Material name.")
    p.add_argument("--library-name", required=True, help="Library name.")
    p.add_argument("--setup-name", default=None, help="Help locate body.")
    _add_common_doc(p)

    p = subcmd(
        "update-setup-machine-params",
        help_text="Update machine params on setup (requires --mode full)",
        desc="Bridge query update_setup_machine_params.",
        epilog=(
            "Example:\n"
            "  fusion-cam --mode full update-setup-machine-params \\\n"
            '    --setup-name "Setup1" \\\n'
            '    --parameters-json \'{"maxSpindleSpeed":"24000 rpm"}\''
        ),
        handler=_h_update_setup_machine_params,
    )
    p.add_argument("--setup-name", required=True, help="Setup name.")
    p.add_argument(
        "--parameters-json",
        type=_json_type_dict,
        required=True,
        help="JSON object: machine param -> expression string.",
    )
    _add_common_doc(p)

    dbg = subcmd(
        "debug",
        help_text="Run arbitrary Python on Fusion main thread",
        desc=(
            "Sends Python to the bridge executor (same as query scripts). "
            "Define run(params) returning data, or set global `result`. "
            "`adsk` and `params` are injected. NOT sandboxed: code can change "
            "the live document. Bridge listens on localhost only."
        ),
        epilog=(
            "Contract (same as queries/*.py):\n"
            "  - Optional: def run(params): return {...}\n"
            "  - Or assign: result = {...}\n"
            "\n"
            "Examples:\n"
            "  fusion-cam debug --code 'result = {\"app\": str(adsk.core.Application.get().activeDocument.name)}'\n"
            "  fusion-cam debug --with-helpers --code 'cam, err = _get_cam(); result = err if err else {\"ok\": True}'\n"
            "  echo 'result = {\"ok\": True}' | fusion-cam debug\n"
            "  fusion-cam debug --file ./probe.py\n"
            "\n"
            "Optional JSON params passed to the script:\n"
            '  fusion-cam debug --params-json \'{"document_name":"MyPart"}\' --code \'def run(p): return p\''
        ),
        handler=_h_debug,
    )
    g = dbg.add_mutually_exclusive_group()
    g.add_argument("--code", default=None, help="Python source string.")
    g.add_argument("--file", dest="code_file", default=None, help="Path to .py file.")
    dbg.add_argument(
        "--params-json",
        type=_json_type_dict,
        default=None,
        help="JSON object available as `params` in the script.",
    )
    dbg.add_argument(
        "--with-helpers",
        action="store_true",
        help="Prepend shared query helpers (_*.py) like named queries do.",
    )

    subcmd(
        "version",
        help_text="Print CLI / package version JSON",
        desc="No Fusion connection required.",
        epilog="Example:\n  fusion-cam version",
        handler=_h_version,
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) >= 1 and argv[0] == "--install":
        from .installer import run_install

        run_install()
        return 0
    if len(argv) >= 1 and argv[0] == "--uninstall":
        from .installer import run_uninstall

        run_uninstall()
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)

    mode = _apply_globals(args)
    handler = args._handler

    if args.command == "version":
        out = handler(None, args)
        _emit(out, args.pretty)
        return _exit_for_result(out)

    session = CamSession(mode)
    try:
        out = handler(session, args)
    finally:
        session.close()

    _emit(out, args.pretty)
    return _exit_for_result(out)


if __name__ == "__main__":
    raise SystemExit(main())
