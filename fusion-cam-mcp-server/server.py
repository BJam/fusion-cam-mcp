"""
Fusion 360 CAM MCP Server

An MCP server that exposes Fusion 360 CAM data (setups, operations, tools,
feeds/speeds, machining times) for AI-assisted manufacturing analysis, with
write capabilities for updating operation parameters, materials, and machine
settings.

All query logic lives in the queries/ directory as Python scripts that are
sent to the Fusion 360 add-in for execution on the main thread. This means
iterating on query logic only requires restarting the MCP server -- no
Fusion add-in restart needed.

Communicates with a Fusion 360 add-in over TCP on localhost.
Runs in stdio mode for Cursor/Claude integration.
"""

__version__ = "0.1.0"

import argparse
import json
import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Add the server directory to sys.path for imports
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from fusion_client import FusionClient
from queries import load_query

# ──────────────────────────────────────────────────────────────────────
# Server mode: "read-only" (default) or "full"
# ──────────────────────────────────────────────────────────────────────

def _parse_mode() -> str:
    """Parse --mode from command line args. Defaults to 'read-only'."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=["read-only", "full"], default="read-only")
    args, _ = parser.parse_known_args()
    return args.mode

SERVER_MODE = _parse_mode()

_READ_ONLY_MESSAGE = (
    "This MCP server is running in read-only mode. Write operations "
    "(updating parameters, assigning materials, etc.) are not available.\n\n"
    "To enable write operations, the user needs to switch to (or enable) "
    "the Fusion 360 CAM MCP server configured with --mode full. "
    "Let the user know they can do this in their Cursor MCP settings."
)


def _require_write_mode() -> str | None:
    """Check if the server is in full mode. Returns an error message if not."""
    if SERVER_MODE != "full":
        return _READ_ONLY_MESSAGE
    return None


# Create the MCP server with mode-aware instructions
_READ_ONLY_INSTRUCTIONS = (
    "Read-only access to Fusion 360 CAM/manufacturing data including "
    "setups, operations, tools, feeds & speeds, machining times, "
    "toolpath status, and post-processing. Use this to analyze and "
    "advise on CNC machining parameters.\n\n"
    "Operations include coolant mode, notes, tool holder info, and "
    "full parameter details organized by category (feeds, speeds, "
    "engagement, linking, drilling, passes, heights, strategy).\n\n"
    "You can also generate toolpaths and post-process to NC/G-code.\n\n"
    "This server is running in READ-ONLY mode. Write tools are visible "
    "but disabled. If the user wants to make changes, let them know they "
    "need to start the MCP server with --mode full."
)

_FULL_INSTRUCTIONS = (
    "Access to Fusion 360 CAM/manufacturing data including setups, "
    "operations, tools, feeds & speeds, machining times, toolpath "
    "status, and post-processing. Use this to analyze and advise on "
    "CNC machining parameters.\n\n"
    "Operations include coolant mode, notes, tool holder info, and "
    "full parameter details organized by category (feeds, speeds, "
    "engagement, linking, drilling, passes, heights, strategy).\n\n"
    "You can generate toolpaths and post-process to NC/G-code.\n\n"
    "Write capabilities are ENABLED. You can update operation feeds/speeds/"
    "engagement, assign physical materials to bodies, and update machine "
    "parameters on setups. All write tools return a before/after diff of "
    "what changed. Always read current values first (get_operations, "
    "get_setups, etc.), propose changes for the user to review, and only "
    "call write tools after the user approves the proposed changes."
)

mcp = FastMCP(
    "Fusion 360 CAM",
    instructions=_FULL_INSTRUCTIONS if SERVER_MODE == "full" else _READ_ONLY_INSTRUCTIONS,
)

# Shared client instance
_client = FusionClient()


# ──────────────────────────────────────────────────────────────────────
# Query execution helpers
# ──────────────────────────────────────────────────────────────────────

def _execute_query(query_name: str, params: dict | None = None) -> dict:
    """Load a query script, send it to the add-in, and return the response."""
    request = load_query(query_name, params)
    try:
        response = _client.send_request(request["action"], {
            "code": request["code"],
            "params": request["params"],
        })
    except ConnectionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}

    return response


def _format_response(response: dict) -> str:
    """Format the add-in response as a string for the MCP tool result."""
    if response.get("success"):
        return json.dumps(response["data"], indent=2)
    else:
        return response.get("error", "Unknown error")


def _run_query(query_name: str, *, write: bool = False, **kwargs) -> str:
    """Execute a query and return the formatted response.

    Builds the params dict from kwargs (filtering out None values),
    optionally checks write mode, and handles error formatting.

    Args:
        query_name: Name of the query script (without .py).
        write: If True, check that write mode is enabled first.
        **kwargs: Query parameters; None values are filtered out.
    """
    if write:
        blocked = _require_write_mode()
        if blocked:
            return blocked

    params = {k: v for k, v in kwargs.items() if v is not None}
    response = _execute_query(query_name, params)
    if not response.get("success"):
        raise RuntimeError(response.get("error", f"Query '{query_name}' failed"))
    return _format_response(response)


# ──────────────────────────────────────────────────────────────────────
# MCP Tool Definitions
# ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def ping() -> str:
    """
    Health check to verify the Fusion 360 CAM MCP add-in connection is alive.
    Call this first to ensure Fusion 360 is running and the add-in is started.
    """
    try:
        response = _client.send_request("ping")
    except ConnectionError as e:
        raise RuntimeError(
            f"Cannot reach Fusion MCP Bridge: {e}"
        )

    if response.get("success"):
        return "Fusion 360 CAM MCP is connected and running."
    else:
        raise RuntimeError(
            f"Cannot reach Fusion MCP Bridge: {response.get('error', 'Unknown error')}"
        )


@mcp.tool()
def list_documents() -> str:
    """
    List all open Fusion 360 documents.

    Returns each document's name, whether it is the currently active (focused)
    document, its units, whether it has CAM data, and counts of setups and
    operations. Use document names from this list as the document_name argument
    to other tools when you want to query a document that is not currently active.
    """
    return _run_query("list_documents")


@mcp.tool()
def get_document_info(document_name: Optional[str] = None) -> str:
    """
    Get information about the active Fusion 360 document.

    Returns the document name, units (mm/in), whether CAM data exists,
    and counts of setups and operations.

    Args:
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
                       Use list_documents to see all open documents.
    """
    return _run_query("get_document_info", document_name=document_name)


@mcp.tool()
def get_setups(document_name: Optional[str] = None) -> str:
    """
    List all CAM setups in the active document.

    Returns each setup's name, type (milling/turning), operation count,
    stock mode, WCS origin, and associated model bodies.
    Use setup names from this list when calling other tools that filter by setup.

    Also includes:
    - Machine info: assigned machine name, spindle RPM range, max feed rates
    - Stock dimensions: mode (fixed box/relative/solid) and X/Y/Z sizes
    - Body materials: physical material assigned to each model body (e.g. "Oak", "Aluminum 6061")

    Machine spindle info (maxSpindleSpeed, minSpindleSpeed, spindlePower,
    peakTorque, peakTorqueSpeed) is read directly from the Machine's
    kinematics tree -- this is the authoritative source for the machine's
    actual spindle capabilities. Use these values (not web lookups) when
    calculating or recommending feeds and speeds.

    Args:
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_setups", document_name=document_name)


@mcp.tool()
def get_operations(
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    List CAM operations with their feeds, speeds, and tool info.

    Returns each operation's name, type (milling/turning/jet/additive),
    strategy, tool details (including presets), feeds & speeds, engagement
    parameters (stepover, stepdown), coolant mode, tool holder info,
    operation notes, and folder path (if the operation is organized in
    a CAM folder within its setup).

    Args:
        setup_name: Optional setup name to filter operations.
                    If not provided, returns operations from all setups.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_operations", setup_name=setup_name, document_name=document_name)


@mcp.tool()
def get_operation_details(
    operation_name: str,
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Get complete parameter details for a specific CAM operation.

    Returns ALL parameters organized by category:
    - Feeds: cutting feed, plunge feed, entry/exit feeds, ramp feed
    - Speeds: spindle RPM, ramp spindle speed
    - Engagement: stepover, stepdown, optimal load
    - Tool: diameter, flute count, lengths, type, holder info, presets
    - Strategy: tolerance, stock to leave, direction, compensation
    - Heights: clearance, retract, feed, top, bottom heights
    - Linking: lead-in/lead-out radii, ramp type/angle, entry/exit positions
    - Drilling: cycle type, dwell time, peck depth, break-through
    - Passes: number of stepdowns, finishing passes, tabs, rest machining

    Each parameter includes its label, value, and metadata flags:
    - isEditable: false if the parameter cannot be changed (omitted when true)
    - isEnabled: false if the parameter is inactive for this strategy (omitted when true)

    Only visible parameters are included in the "other" (uncategorized) bucket.

    Also includes: coolant mode, operation notes, and computed metrics:
    - Surface speed (SFM / m/min)
    - Chip load (per tooth)
    - Stepover-to-diameter ratio

    Args:
        operation_name: The exact name of the operation (from get_operations).
        setup_name: Optional setup name to narrow the search.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query(
        "get_operation_details",
        operation_name=operation_name,
        setup_name=setup_name,
        document_name=document_name,
    )


@mcp.tool()
def get_tools(document_name: Optional[str] = None) -> str:
    """
    List all cutting tools from the document's tool library.

    Returns each tool's number, type, diameter, flute count, lengths,
    which operations use it, and any tool presets (material-specific
    feeds/speeds recommendations from the tool manufacturer).
    Sources tools from the DocumentToolLibrary for the complete inventory,
    including tools not currently assigned to any operation.

    Args:
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_tools", document_name=document_name)


@mcp.tool()
def get_library_tools(
    location: Optional[str] = None,
    library_name: Optional[str] = None,
    tool_type: Optional[str] = None,
    min_diameter: Optional[float] = None,
    max_diameter: Optional[float] = None,
) -> str:
    """
    Browse cutting tools from Fusion 360's CAMLibraryManager tool libraries.

    Unlike get_tools (which reads the document-embedded tool library), this
    tool reads the "external" libraries available in the Fusion 360 tool
    library manager — your local library, Autodesk's bundled Fusion 360
    libraries, cloud libraries, and hub/team libraries. Use this to find
    alternative tools you own but haven't yet assigned to an operation.

    Diameter values are in Fusion's internal units (cm). For example, a
    12 mm end mill has tool_diameter ≈ 1.2 (cm).

    Args:
        location: Which library root to query. One of:
                    "local"     - tools saved on this machine (default)
                    "fusion360" - Autodesk-supplied sample/reference libs
                    "cloud"     - Autodesk cloud library
                    "hub"       - team/hub shared library
        library_name: Optional substring to filter by library filename
                      (e.g. "Metric", "Inch", "Harvey"). Case-insensitive.
        tool_type: Optional substring to filter by tool type
                   (e.g. "flat end mill", "ball end mill", "drill").
                   Case-insensitive.
        min_diameter: Optional minimum tool diameter in cm (e.g. 0.6 for 6 mm).
        max_diameter: Optional maximum tool diameter in cm (e.g. 2.5 for 25 mm).
    """
    return _run_query(
        "get_library_tools",
        location=location or "local",
        library_name=library_name,
        tool_type=tool_type,
        min_diameter=min_diameter,
        max_diameter=max_diameter,
    )


@mcp.tool()
def get_machining_time(
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Get estimated machining time for setups and operations.

    Returns machining time, rapid time, and total time for each operation,
    plus a total per setup. Times are in seconds with human-readable formatting.

    Args:
        setup_name: Optional setup name to check a specific setup.
                    If not provided, returns times for all setups.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_machining_time", setup_name=setup_name, document_name=document_name)


@mcp.tool()
def get_toolpath_status(
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Check toolpath generation status for all operations.

    Returns whether each operation has a generated toolpath, if the
    toolpath is valid/current or needs regeneration, and any warnings.
    Includes a summary with counts of valid, outdated, and suppressed operations.

    Args:
        setup_name: Optional setup name to check a specific setup.
                    If not provided, returns status for all operations.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_toolpath_status", setup_name=setup_name, document_name=document_name)


@mcp.tool()
def get_nc_programs(document_name: Optional[str] = None) -> str:
    """
    List all NC programs configured in the document.

    NC programs are Fusion 360's built-in way to group operations for
    post-processing with specific output settings. Returns each program's
    name, associated operations, post-processor configuration, and output
    settings (filename, program number).

    Args:
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query("get_nc_programs", document_name=document_name)


@mcp.tool()
def generate_toolpaths(
    setup_name: Optional[str] = None,
    operation_names: Optional[list[str]] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Generate toolpaths for CAM operations.

    Triggers toolpath generation and waits for completion (up to 5 minutes).
    Use this after updating feeds/speeds or other parameters to regenerate
    toolpaths, or to generate toolpaths for new operations.

    Can target specific operations by name, all operations in a setup,
    or all operations in the document. Suppressed operations are skipped
    automatically when targeting a setup or document.

    Args:
        setup_name: Optional setup name to generate toolpaths for all
                    operations in that setup.
        operation_names: Optional list of specific operation names to generate.
                         Takes priority over setup_name for targeting.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query(
        "generate_toolpaths",
        setup_name=setup_name,
        operation_names=operation_names,
        document_name=document_name,
    )


@mcp.tool()
def post_process(
    setup_name: str,
    output_folder: str,
    program_name: Optional[str] = None,
    program_number: Optional[int] = None,
    operation_names: Optional[list[str]] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Post-process a setup or specific operations to generate NC/G-code files.

    Uses the post processor configured on the setup's machine. All targeted
    operations must have valid generated toolpaths before post-processing.

    Returns the output folder path, post processor used, list of operations
    processed, and generated file names with sizes.

    Args:
        setup_name: The setup to post-process (from get_setups).
        output_folder: Absolute path to the folder where NC files will be written.
        program_name: Optional program name for the NC output. Defaults to the setup name.
        program_number: Optional program number (O-number). Defaults to 1001.
        operation_names: Optional list of specific operation names to post-process.
                         If not provided, all non-suppressed operations in the setup are used.
        document_name: Optional document name to query a specific open document.
                       If not provided, uses the currently active (focused) document.
    """
    return _run_query(
        "post_process",
        setup_name=setup_name,
        output_folder=output_folder,
        program_name=program_name,
        program_number=program_number,
        operation_names=operation_names,
        document_name=document_name,
    )


# ──────────────────────────────────────────────────────────────────────
# Write MCP Tool Definitions
# ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def update_operation_parameters(
    operation_name: str,
    parameters: dict,
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Update feeds, speeds, and/or engagement parameters on a CAM operation.

    Applies the changes and returns a before/after diff showing exactly what
    changed. Use get_operations or get_operation_details first to see current
    values, then propose changes for the user to review before calling this.

    The parameters dict maps CAM parameter names to expression strings using
    Fusion's format with explicit units, e.g.:
      {"tool_feedCutting": "750 mm/min", "tool_spindleSpeed": "12000 rpm"}

    Writable parameter names (feeds):
      tool_feedCutting, tool_feedEntry, tool_feedExit, tool_feedPlunge,
      tool_feedRamp, tool_feedRetract, tool_feedTransition, tool_feedPerTooth

    Writable parameter names (speeds):
      tool_spindleSpeed, tool_rampSpindleSpeed, tool_clockwise

    Writable parameter names (engagement):
      stepover, stepdown, finishStepover, finishStepdown, optimalLoad,
      loadDeviation, maximumStepdown, fineStepdown

    Args:
        operation_name: The exact name of the operation (from get_operations).
        parameters: Dict of {param_name: expression_string} to update.
        setup_name: Optional setup name to narrow the search.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "update_operation_params",
        write=True,
        operation_name=operation_name,
        parameters=parameters,
        setup_name=setup_name,
        document_name=document_name,
    )


@mcp.tool()
def list_material_libraries(
    library_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Browse available physical/design material libraries and their materials.

    These are physical materials (density, strength, thermal properties) used
    for simulation and body material assignment -- NOT CAM stock materials.
    Use this to discover valid material names and library names before
    assigning a material to a body with assign_body_material.

    If library_name is provided, returns materials within that specific library.
    Otherwise returns all libraries with their material counts and names.

    Args:
        library_name: Optional library name to list materials from a specific library.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "list_material_libraries",
        library_name=library_name,
        document_name=document_name,
    )


@mcp.tool()
def get_material_properties(
    material_name: str,
    library_name: str,
    document_name: Optional[str] = None,
) -> str:
    """
    Read all physical/mechanical properties of a specific design material.

    Returns every property (density, Young's modulus, Poisson's ratio,
    yield/tensile strength, thermal conductivity, etc.) with names,
    values, and units. These are physical material properties used for
    simulation -- useful for inspecting existing materials before
    creating custom ones.

    Args:
        material_name: Name of the material (from list_material_libraries).
        library_name: Name of the library containing the material.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "get_material_properties",
        material_name=material_name,
        library_name=library_name,
        document_name=document_name,
    )


@mcp.tool()
def create_custom_material(
    new_material_name: str,
    source_material_name: str,
    source_library_name: str,
    property_overrides: dict,
    assign_to_bodies: Optional[list] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Create a new custom material by copying an existing one and overriding properties.

    Copies the source material into the document's Custom Library, renames it,
    then applies property overrides. Returns the new material's properties.

    Use get_material_properties first to inspect the source material's property
    names and values, then specify overrides using those exact property names.

    The property_overrides dict maps property names to new values, e.g.:
      {"structural_Density": 745.0, "structural_Young_modulus": 13070000000.0}

    Args:
        new_material_name: Name for the new custom material.
        source_material_name: Name of the material to copy from.
        source_library_name: Name of the library containing the source material.
        property_overrides: Dict of {property_name: new_value} to override.
        assign_to_bodies: Optional list of body names to assign the new material to.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "create_custom_material",
        write=True,
        new_material_name=new_material_name,
        source_material_name=source_material_name,
        source_library_name=source_library_name,
        property_overrides=property_overrides,
        assign_to_bodies=assign_to_bodies,
        document_name=document_name,
    )


@mcp.tool()
def assign_body_material(
    body_name: str,
    material_name: str,
    library_name: str,
    setup_name: Optional[str] = None,
    document_name: Optional[str] = None,
) -> str:
    """
    Assign a physical/design material from a library to a body.

    This sets the body's physical material (density, strength, etc.) used
    for mass properties and simulation -- it does NOT set the CAM stock
    material. Returns a before/after diff showing the old and new assignment.
    Use list_material_libraries to discover valid library and material names.
    Use get_setups to see current body materials and body names.

    Args:
        body_name: Name of the body to assign material to (from get_setups models list).
        material_name: Name of the material to assign (from list_material_libraries).
        library_name: Name of the material library containing the material.
        setup_name: Optional setup name to help locate the body.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "assign_body_material",
        write=True,
        body_name=body_name,
        material_name=material_name,
        library_name=library_name,
        setup_name=setup_name,
        document_name=document_name,
    )


@mcp.tool()
def update_setup_machine_params(
    setup_name: str,
    parameters: dict,
    document_name: Optional[str] = None,
) -> str:
    """
    Update machine-level parameters on a CAM setup.

    Applies the changes and returns a before/after diff showing exactly what
    changed. Use get_setups first to see current machine configuration.

    The parameters dict maps machine parameter names to expression strings, e.g.:
      {"maxSpindleSpeed": "24000 rpm", "machine_dimension_x": "500 mm"}

    Writable machine parameter names:
      machine_dimension_x, machine_dimension_y, machine_dimension_z,
      machineMaxTilt

    Writable parameter names (spindle):
      maxSpindleSpeed, minSpindleSpeed, spindlePower,
      peakTorque, peakTorqueSpeed

    Args:
        setup_name: The exact name of the setup (from get_setups).
        parameters: Dict of {param_name: expression_string} to update.
        document_name: Optional document name to query a specific open document.
    """
    return _run_query(
        "update_setup_machine_params",
        write=True,
        setup_name=setup_name,
        parameters=parameters,
        document_name=document_name,
    )


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--install" in sys.argv:
        from installer import run_install
        try:
            run_install()
        except Exception as e:
            print(f"\n  ERROR: Install failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        sys.exit(0)
    elif "--uninstall" in sys.argv:
        from installer import run_uninstall
        try:
            run_uninstall()
        except Exception as e:
            print(f"\n  ERROR: Uninstall failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
        sys.exit(0)
    else:
        mcp.run()
