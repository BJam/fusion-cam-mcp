# ──────────────────────────────────────────────────────────────────────
# Shared helpers for Fusion 360 CAM query scripts.
#
# This file is prepended to each query script before execution inside
# Fusion 360. It provides constants, parameter mappings, and utility
# functions that multiple queries share.
#
# Available in the namespace: adsk (module), params (dict).
# Each query script defines  def run(params) -> dict  as its entry point.
#
# ── Public API for query scripts ──────────────────────────────────────
#
# Constants:
#   CAM_PRODUCT_TYPE           - Product type string for CAM workspace
#   DISTANCE_UNIT_MAP          - Enum int → unit label mapping
#   DEFAULT_RAPID_FEED         - Default rapid feed for time estimation
#   DEFAULT_TOOL_CHANGE_TIME   - Default tool change time (seconds)
#   OPERATION_TYPE_MAP         - Setup operationType enum → label
#   FEED_PARAMS, SPEED_PARAMS, ENGAGEMENT_PARAMS, TOOL_GEOM_PARAMS,
#   STRATEGY_PARAMS, LINKING_PARAMS, DRILLING_PARAMS, PASS_PARAMS,
#   HEIGHT_PARAMS              - Parameter name → human label mappings
#   ALL_PARAM_CATEGORIES       - All above grouped by category name
#   WRITABLE_OPERATION_PARAMS  - Feeds + speeds + engagement (writable)
#   MACHINE_WRITABLE_PARAMS    - Machine dimensions (writable)
#   SPINDLE_WRITABLE_PARAMS    - Spindle attributes (writable)
#
# Document / CAM access:
#   _get_document(name)        - Returns (doc, error_dict)
#   _get_cam(name)             - Returns (cam, error_dict)
#   _get_document_units(doc)   - Returns unit string ("mm", "in", …)
#
# Object lookup:
#   _find_setup_by_name(cam, name)
#   _find_operation_by_name(cam, name, setup_name)
#   _build_folder_map(setup)            - Operation name → folder path
#   _find_body_by_name(doc_name, body_name, setup_name)
#   _find_library_by_name(library_name)
#   _find_material_in_library(library_name, material_name)
#
# Parameter read/write:
#   _read_param(params, name)           - Safe single-param read
#   _read_param_raw(params, name)       - Raw .value read
#   _safe_param_value(param)            - Full type-aware extraction
#   _write_param(params, name, expr)    - Set by expression string
#   _capture_param_snapshot(params, names)
#   _build_diff(before, after, labels)
#
# Machine spindle:
#   _read_machine_spindle(machine)      - Read spindle from kinematics
#   _write_machine_spindle(machine, name, value)
#
# Operation helpers:
#   _get_tool_info(op)                  - Tool + holder + presets data
#   _get_tool_presets(tool)             - Material-specific presets
#   _get_coolant_info(op)               - Coolant mode string
#   _get_operation_summary(op)          - Standard summary dict
#
# Material helpers:
#   _read_all_material_properties(mat)  - All props as list of dicts
#
# Write guards:
#   _check_no_active_command()          - Prevents writes during dialogs
#
# Formatting:
#   _format_time(seconds)               - Human-readable time string
# ──────────────────────────────────────────────────────────────────────

import adsk.core
import adsk.fusion
import adsk.cam
import math

# ──────────────────────────────────────────────────────────────────────
# CAM parameter name mapping
# ──────────────────────────────────────────────────────────────────────

FEED_PARAMS = {
    "tool_feedCutting":     "Cutting Feed Rate",
    "tool_feedEntry":       "Entry Feed Rate",
    "tool_feedExit":        "Exit Feed Rate",
    "tool_feedPlunge":      "Plunge Feed Rate",
    "tool_feedRamp":        "Ramp Feed Rate",
    "tool_feedRetract":     "Retract Feed Rate",
    "tool_feedTransition":  "Transition Feed Rate",
    "tool_feedPerTooth":    "Feed Per Tooth",
}

SPEED_PARAMS = {
    "tool_spindleSpeed":      "Spindle Speed (RPM)",
    "tool_rampSpindleSpeed":  "Ramp Spindle Speed (RPM)",
    "tool_clockwise":         "Spindle Direction Clockwise",
}

ENGAGEMENT_PARAMS = {
    "stepover":              "Radial Stepover",
    "stepdown":              "Axial Stepdown",
    "finishStepover":        "Finish Stepover",
    "finishStepdown":        "Finish Stepdown",
    "optimalLoad":           "Optimal Load (Adaptive)",
    "loadDeviation":         "Load Deviation",
    "maximumStepdown":       "Maximum Stepdown",
    "fineStepdown":          "Fine Stepdown",
}

TOOL_GEOM_PARAMS = {
    "tool_diameter":          "Tool Diameter",
    "tool_numberOfFlutes":    "Number of Flutes",
    "tool_fluteLength":       "Flute Length",
    "tool_overallLength":     "Overall Length",
    "tool_shoulderLength":    "Shoulder Length",
    "tool_shaftDiameter":     "Shaft Diameter",
    "tool_type":              "Tool Type",
    "tool_number":            "Tool Number",
    "tool_comment":           "Tool Comment",
    "tool_description":       "Tool Description",
    "tool_bodyLength":        "Body Length",
    "tool_cornerRadius":      "Corner Radius",
    "tool_taperAngle":        "Taper Angle",
    "tool_tipAngle":          "Tip Angle",
}

STRATEGY_PARAMS = {
    "tolerance":              "Tolerance",
    "contourTolerance":       "Contour Tolerance",
    "smoothingTolerance":     "Smoothing Tolerance",
    "useStockToLeave":        "Use Stock To Leave",
    "stockToLeave":           "Radial Stock To Leave",
    "axialStockToLeave":      "Axial Stock To Leave",
    "finishStockToLeave":     "Finish Radial Stock To Leave",
    "finishAxialStockToLeave":"Finish Axial Stock To Leave",
    "bothWays":               "Both Ways (Zigzag)",
    "machineShallowAreas":    "Machine Shallow Areas",
    "machineSteepAreas":      "Machine Steep Areas",
    "direction":              "Direction",
    "compensation":           "Compensation",
    "compensationType":       "Compensation Type",
}

LINKING_PARAMS = {
    "leadInRadius":           "Lead-In Radius",
    "leadOutRadius":          "Lead-Out Radius",
    "leadInSweepAngle":       "Lead-In Sweep Angle",
    "leadOutSweepAngle":      "Lead-Out Sweep Angle",
    "leadInVerticalRadius":   "Lead-In Vertical Radius",
    "leadOutVerticalRadius":  "Lead-Out Vertical Radius",
    "rampType":               "Ramp Type",
    "rampAngle":              "Helical Ramp Angle",
    "rampDiameter":           "Helical Ramp Diameter",
    "rampClearanceHeight":    "Ramp Clearance Height",
    "entryPositionType":      "Entry Position Type",
    "exitPositionType":       "Exit Position Type",
    "useRetracts":            "Use Retracts",
    "keepToolDown":           "Keep Tool Down",
    "liftHeight":             "Lift Height",
}

DRILLING_PARAMS = {
    "cycleType":              "Drill Cycle Type",
    "dwellTime":              "Dwell Time",
    "dwellEnabled":           "Dwell Enabled",
    "peckingDepth":           "Peck Depth",
    "accumulatedPeckingDepth":"Accumulated Peck Depth",
    "chipBreakDistance":      "Chip Break Distance",
    "breakThroughDistance":   "Break Through Distance",
    "breakThroughFeedrate":   "Break Through Feed Rate",
    "backBoreDistance":       "Back Bore Distance",
    "threading":              "Threading",
    "pitch":                  "Thread Pitch",
}

PASS_PARAMS = {
    "numberOfStepdowns":      "Number of Stepdowns",
    "useFinishingPasses":     "Use Finishing Passes",
    "finishingPasses":        "Finishing Pass Count",
    "doMultipleDepths":       "Multiple Depth Passes",
    "restMachining":          "Rest Machining",
    "restMachiningAdjustment":"Rest Machining Adjustment",
    "useTabbing":             "Use Tabs",
    "tabWidth":               "Tab Width",
    "tabHeight":              "Tab Height",
    "tabCount":               "Tab Count",
    "tabPositioning":         "Tab Positioning",
}

HEIGHT_PARAMS = {
    "clearanceHeight_value":   "Clearance Height",
    "clearanceHeight_offset":  "Clearance Height Offset",
    "retractHeight_value":     "Retract Height",
    "retractHeight_offset":    "Retract Height Offset",
    "feedHeight_value":        "Feed Height",
    "feedHeight_offset":       "Feed Height Offset",
    "topHeight_value":         "Top Height",
    "topHeight_offset":        "Top Height Offset",
    "bottomHeight_value":      "Bottom Height",
    "bottomHeight_offset":     "Bottom Height Offset",
}

# Machine-related parameter names to read from setups.
# Note: Spindle speed/feedrate limits are NOT setup parameters -- they live
# on the Machine's kinematics tree (MachineSpindle object).  See
# _read_machine_spindle() and _write_machine_spindle() for those.
_MACHINE_PARAM_NAMES = [
    "job_machine",
    "job_machine_manufacturer",
    "job_machine_type",
    "job_machine_configuration",
    "job_machine_configuration_id",
    "job_machine_build_strategy_id",
    "machine_dimension_x",
    "machine_dimension_y",
    "machine_dimension_z",
    "machineMaxTilt",
]

# Stock-related parameter names to read from setups.
_STOCK_PARAM_NAMES = [
    "job_stockMode",
    "job_stockFixedX",
    "job_stockFixedY",
    "job_stockFixedZ",
    "job_stockFixed_width",
    "job_stockFixed_height",
    "job_stockFixed_depth",
    "job_stockOffsetSide",
    "job_stockOffsetTop",
    "job_stockOffsetBottom",
    "job_stockExpandX",
    "job_stockExpandY",
    "job_stockExpandZ",
    "job_stockDiameter",
    "job_stockLength",
    "job_stockType",
]

# Combined mapping of all known parameters
ALL_PARAM_CATEGORIES = {
    "feeds":      FEED_PARAMS,
    "speeds":     SPEED_PARAMS,
    "engagement": ENGAGEMENT_PARAMS,
    "tool":       TOOL_GEOM_PARAMS,
    "strategy":   STRATEGY_PARAMS,
    "heights":    HEIGHT_PARAMS,
    "linking":    LINKING_PARAMS,
    "drilling":   DRILLING_PARAMS,
    "passes":     PASS_PARAMS,
}

ALL_KNOWN_PARAMS = {}
for _cat_params in ALL_PARAM_CATEGORIES.values():
    ALL_KNOWN_PARAMS.update(_cat_params)

# Product type constant
CAM_PRODUCT_TYPE = "CAMProductType"

# adsk.cam.OperationTypes enum → human-readable string
OPERATION_TYPE_MAP = {
    0: "milling",
    1: "turning",
    2: "jet",
    3: "additive",
}

# Fusion distance display units enum → string label
DISTANCE_UNIT_MAP = {0: "mm", 1: "cm", 2: "m", 3: "in", 4: "ft"}

# Defaults for machining time estimation (used by get_machining_time)
DEFAULT_RAPID_FEED = 500.0       # cm/min (~200 ipm)
DEFAULT_TOOL_CHANGE_TIME = 15.0  # seconds


# ──────────────────────────────────────────────────────────────────────
# Utility functions
# ──────────────────────────────────────────────────────────────────────

def _get_document(document_name=None):
    """Get a document by name, or the active document.
    Returns (document, error_dict) tuple.
    """
    app = adsk.core.Application.get()
    if not app:
        return None, {"success": False, "error": "Fusion 360 application not available"}

    if document_name:
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            if doc.name == document_name:
                return doc, None
        available = [app.documents.item(i).name for i in range(app.documents.count)]
        return None, {
            "success": False,
            "error": f"Document '{document_name}' not found. Open documents: {available}. "
                     f"Use list_documents to see all open documents."
        }
    else:
        doc = app.activeDocument
        if not doc:
            return None, {"success": False, "error": "No document is open in Fusion 360"}
        return doc, None


def _get_cam(document_name=None):
    """Get a CAM product, optionally from a specific document.
    Returns (cam, error_dict) tuple.
    """
    doc, err = _get_document(document_name)
    if err:
        return None, err

    cam_product = doc.products.itemByProductType(CAM_PRODUCT_TYPE)
    if not cam_product:
        return None, {
            "success": False,
            "error": f"No CAM workspace found in document '{doc.name}'. "
                     f"Switch to the Manufacturing workspace first."
        }

    cam = adsk.cam.CAM.cast(cam_product)
    if not cam:
        return None, {"success": False, "error": "Failed to cast to CAM product"}

    return cam, None


def _get_document_units(doc):
    """Get display units for a document as a short string (mm, in, etc.)."""
    try:
        design = adsk.fusion.Design.cast(
            doc.products.itemByProductType("DesignProductType")
        )
        if design and design.fusionUnitsManager:
            dist_units = design.fusionUnitsManager.distanceDisplayUnits
            return DISTANCE_UNIT_MAP.get(dist_units, str(dist_units))
    except Exception:
        pass
    return "unknown"


def _safe_param_value(param):
    """Safely extract a parameter value, handling different parameter types."""
    if param is None:
        return None
    try:
        expr = None
        try:
            expr = param.expression
        except Exception:
            pass

        val = param.value
        if hasattr(val, "value"):
            val = val.value

        if isinstance(val, bool):
            return val
        elif isinstance(val, (int, float)):
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return str(val)
            return {"value": val, "expression": expr if expr else str(val)}
        elif isinstance(val, str):
            return val
        else:
            return str(val) if val is not None else None
    except Exception:
        try:
            val = param.value
            if hasattr(val, "value"):
                val = val.value
            return str(val) if val is not None else None
        except Exception:
            return None


def _read_param(params, name):
    """Read a single parameter by name, returning None if not found."""
    try:
        param = params.itemByName(name)
        if param is None:
            return None
        return _safe_param_value(param)
    except Exception:
        return None


def _read_param_raw(params, name):
    """Read a raw parameter value (just the .value), useful for tool params."""
    try:
        param = params.itemByName(name)
        if param is None:
            return None
        val = param.value
        if hasattr(val, "value"):
            return val.value
        return val
    except Exception:
        return None


def _is_proxy_str(val):
    """Check if a value is a Swig proxy string (not useful as serialized data)."""
    if isinstance(val, str):
        return "<adsk." in val or "proxy of" in val or "Swig Object" in val
    return False


def _read_machine_spindle(machine_obj):
    """Read spindle data from machine.kinematics.parts tree.

    Walks the kinematics parts and their children looking for the first
    part that has a spindle assigned. Returns a dict with maxSpeed,
    minSpeed, power, peakTorque, peakTorqueSpeed, and description,
    or None if no spindle is found.

    The Fusion 360 Machine object stores spindle data on MachinePart
    objects in the kinematics tree, NOT as setup parameters.
    """
    try:
        kin = machine_obj.kinematics
        if not kin:
            return None
        parts = kin.parts
        if not parts:
            return None

        def _check_part(part):
            sp = getattr(part, "spindle", None)
            if sp:
                data = {}
                for attr, label, unit in [
                    ("maxSpeed", "maxSpindleSpeed", "rpm"),
                    ("minSpeed", "minSpindleSpeed", "rpm"),
                    ("power", "spindlePower", "kW"),
                    ("peakTorque", "peakTorque", "Nm"),
                    ("peakTorqueSpeed", "peakTorqueSpeed", "rpm"),
                ]:
                    try:
                        val = getattr(sp, attr, None)
                        if val is not None:
                            data[label] = {"value": val, "unit": unit}
                    except Exception:
                        pass
                try:
                    desc = sp.description
                    if desc:
                        data["description"] = desc
                except Exception:
                    pass
                return data
            # Check children
            try:
                children = getattr(part, "children", None)
                if children:
                    count = getattr(children, "count", 0)
                    for i in range(count):
                        child_result = _check_part(children.item(i))
                        if child_result:
                            return child_result
            except Exception:
                pass
            return None

        count = getattr(parts, "count", 0)
        for i in range(count):
            result = _check_part(parts.item(i))
            if result:
                return result
    except Exception:
        pass
    return None


def _write_machine_spindle(machine_obj, param_name, value):
    """Write a spindle parameter on the machine's kinematics tree.

    Supported param_name values:
        maxSpindleSpeed, minSpindleSpeed, spindlePower,
        peakTorque, peakTorqueSpeed

    Args:
        machine_obj: adsk.cam.Machine instance.
        param_name: One of the supported spindle parameter names.
        value: The numeric value to set (float).

    Returns:
        (success: bool, error_message: str or None)
    """
    SPINDLE_PARAM_MAP = {
        "maxSpindleSpeed": "maxSpeed",
        "minSpindleSpeed": "minSpeed",
        "spindlePower": "power",
        "peakTorque": "peakTorque",
        "peakTorqueSpeed": "peakTorqueSpeed",
    }
    attr_name = SPINDLE_PARAM_MAP.get(param_name)
    if not attr_name:
        return False, f"Unknown spindle parameter '{param_name}'. Valid: {sorted(SPINDLE_PARAM_MAP.keys())}"

    try:
        kin = machine_obj.kinematics
        if not kin:
            return False, "Machine has no kinematics object"
        parts = kin.parts
        if not parts:
            return False, "Machine kinematics has no parts"

        def _find_spindle(part):
            sp = getattr(part, "spindle", None)
            if sp:
                return sp
            try:
                children = getattr(part, "children", None)
                if children:
                    count = getattr(children, "count", 0)
                    for i in range(count):
                        found = _find_spindle(children.item(i))
                        if found:
                            return found
            except Exception:
                pass
            return None

        spindle = None
        count = getattr(parts, "count", 0)
        for i in range(count):
            spindle = _find_spindle(parts.item(i))
            if spindle:
                break

        if not spindle:
            return False, "No spindle found in machine kinematics tree"

        setattr(spindle, attr_name, float(value))
        return True, None
    except Exception as e:
        return False, f"Failed to set spindle.{attr_name}: {e}"


# Spindle parameters that can be written via _write_machine_spindle.
SPINDLE_WRITABLE_PARAMS = {
    "maxSpindleSpeed":  "Max Spindle Speed (RPM)",
    "minSpindleSpeed":  "Min Spindle Speed (RPM)",
    "spindlePower":     "Spindle Power (kW)",
    "peakTorque":       "Peak Torque (Nm)",
    "peakTorqueSpeed":  "Peak Torque Speed (RPM)",
}


def _get_tool_info(op):
    """Extract tool information from an operation, including holder and coolant."""
    try:
        tool = op.tool
        if not tool:
            return None

        tool_params = tool.parameters
        info = {}
        for key in TOOL_GEOM_PARAMS:
            val = _read_param_raw(tool_params, key)
            if val is not None:
                info[key] = val

        try:
            info["tool_typeName"] = str(tool.type)
        except Exception:
            pass

        # Tool holder info
        try:
            holder = tool.holder
            if holder:
                holder_info = {}
                try:
                    holder_info["description"] = holder.description
                except Exception:
                    pass
                try:
                    holder_params = holder.parameters
                    for i in range(holder_params.count):
                        p = holder_params.item(i)
                        val = p.value
                        if hasattr(val, "value"):
                            val = val.value
                        if val is not None and not _is_proxy_str(str(val)):
                            holder_info[p.name] = val
                except Exception:
                    pass
                if holder_info:
                    info["holder"] = holder_info
        except Exception:
            pass

        presets = _get_tool_presets(tool)
        if presets:
            info["presets"] = presets

        return info
    except Exception:
        return None


def _get_tool_presets(tool):
    """Extract presets (material-specific feeds/speeds) from a Tool object.

    Returns a list of preset dicts, each with name, id, and the feed/speed
    parameters that differ from the base tool settings. Returns an empty
    list if the tool has no presets.
    """
    presets = []
    try:
        preset_coll = tool.presets
        if not preset_coll:
            return presets
        for i in range(preset_coll.count):
            preset = preset_coll.item(i)
            entry = {}
            try:
                entry["name"] = preset.name
            except Exception:
                pass
            try:
                entry["id"] = preset.id
            except Exception:
                pass
            # Read feeds/speeds from the preset parameters
            try:
                pp = preset.parameters
                fs = {}
                for key in list(FEED_PARAMS.keys()) + list(SPEED_PARAMS.keys()):
                    val = _read_param(pp, key)
                    if val is not None:
                        fs[key] = val
                if fs:
                    entry["feedsAndSpeeds"] = fs
            except Exception:
                pass
            # Read engagement params
            try:
                pp = preset.parameters
                eng = {}
                for key in ENGAGEMENT_PARAMS:
                    val = _read_param(pp, key)
                    if val is not None:
                        eng[key] = val
                if eng:
                    entry["engagement"] = eng
            except Exception:
                pass
            if entry:
                presets.append(entry)
    except Exception:
        pass
    return presets


def _get_coolant_info(op):
    """Extract coolant mode from an operation."""
    try:
        tool = op.tool
        if not tool:
            return None
        coolant_val = _read_param_raw(tool.parameters, "tool_coolant")
        if coolant_val is not None:
            return str(coolant_val)
        # Fallback: try reading from operation parameters
        op_coolant = _read_param(op.parameters, "tool_coolant")
        if op_coolant is not None:
            return str(op_coolant) if not isinstance(op_coolant, str) else op_coolant
    except Exception:
        pass
    return None


def _get_operation_summary(op):
    """Build a summary dict for an operation."""
    op_params = op.parameters

    op_type = None
    try:
        parent = op.parentSetup
        if parent:
            op_type = OPERATION_TYPE_MAP.get(
                parent.operationType, str(parent.operationType)
            )
    except Exception:
        pass

    summary = {
        "name": op.name,
        "type": op_type,
        "strategy": str(op.strategy) if hasattr(op, "strategy") else None,
        "isSuppressed": op.isSuppressed,
        "hasToolpath": op.hasToolpath,
    }

    # Operation notes
    try:
        notes = op.notes
        if notes:
            summary["notes"] = notes
    except Exception:
        pass

    tool_info = _get_tool_info(op)
    if tool_info:
        summary["tool"] = tool_info

    # Coolant mode
    coolant = _get_coolant_info(op)
    if coolant:
        summary["coolant"] = coolant

    feeds_speeds = {}
    for key in FEED_PARAMS:
        val = _read_param(op_params, key)
        if val is not None:
            feeds_speeds[key] = val
    for key in SPEED_PARAMS:
        val = _read_param(op_params, key)
        if val is not None:
            feeds_speeds[key] = val

    if feeds_speeds:
        summary["feedsAndSpeeds"] = feeds_speeds

    engagement = {}
    for key in ENGAGEMENT_PARAMS:
        val = _read_param(op_params, key)
        if val is not None:
            engagement[key] = val

    if engagement:
        summary["engagement"] = engagement

    try:
        if op.hasToolpath:
            summary["isToolpathValid"] = op.isToolpathValid
    except Exception:
        pass

    return summary


def _build_folder_map(setup):
    """Walk a setup's child tree and map operation names to folder paths.

    Returns a dict of {operation_name: folder_path} where folder_path is
    the slash-separated path from the setup root (e.g. "Roughing/Walls").
    Operations at the setup root have no entry in the map.
    """
    folder_map = {}

    def _walk(children, path):
        if not children:
            return
        for i in range(children.count):
            child = children.item(i)
            try:
                child_folder = adsk.cam.CAMFolder.cast(child)
                if child_folder:
                    sub_path = f"{path}/{child_folder.name}" if path else child_folder.name
                    try:
                        _walk(child_folder.children, sub_path)
                    except Exception:
                        pass
                    continue
            except Exception:
                pass
            try:
                child_op = adsk.cam.Operation.cast(child)
                if child_op and path:
                    folder_map[child_op.name] = path
            except Exception:
                pass

    try:
        _walk(setup.children, "")
    except Exception:
        pass
    return folder_map


def _find_setup_by_name(cam, name):
    """Find a setup by name. Returns (setup, error_dict) tuple."""
    for setup in cam.setups:
        if setup.name == name:
            return setup, None
    return None, {
        "success": False,
        "error": f"Setup '{name}' not found. Use get_setups to list available setups."
    }


def _find_operation_by_name(cam, operation_name, setup_name=None):
    """Find an operation by name, optionally within a specific setup."""
    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return None, err
        for op in setup.allOperations:
            if op.name == operation_name:
                return op, None
        return None, {
            "success": False,
            "error": f"Operation '{operation_name}' not found in setup '{setup_name}'."
        }
    else:
        for op in cam.allOperations:
            if op.name == operation_name:
                return op, None
        return None, {
            "success": False,
            "error": f"Operation '{operation_name}' not found. Use get_operations to list available operations."
        }


def _format_time(seconds):
    """Format seconds into a human-readable string."""
    if seconds is None or seconds == 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _find_library_by_name(library_name):
    """Find a material library by name.
    Returns (library, error_dict) tuple.
    """
    app = adsk.core.Application.get()
    if not app:
        return None, {"success": False, "error": "Fusion 360 application not available"}
    mat_libs = app.materialLibraries
    for i in range(mat_libs.count):
        lib = mat_libs.item(i)
        if lib.name == library_name:
            return lib, None
    available = [mat_libs.item(i).name for i in range(mat_libs.count)]
    return None, {
        "success": False,
        "error": f"Material library '{library_name}' not found. "
                 f"Available libraries: {available}"
    }


def _find_material_in_library(library_name, material_name):
    """Find a material in a named library.
    Returns (material, error_dict) tuple.
    """
    lib, err = _find_library_by_name(library_name)
    if err:
        return None, err
    for j in range(lib.materials.count):
        mat = lib.materials.item(j)
        if mat.name == material_name:
            return mat, None
    return None, {
        "success": False,
        "error": f"Material '{material_name}' not found in library '{library_name}'. "
                 f"Use list_material_libraries to browse."
    }


def _read_all_material_properties(material):
    """Read all physical/mechanical properties from a material object.
    Returns a list of dicts with name, id, value, and units.
    """
    props = []
    mat_props = material.materialProperties
    for k in range(mat_props.count):
        p = mat_props.item(k)
        p_info = {"name": p.name}
        try:
            p_info["id"] = p.id
        except Exception:
            pass
        try:
            val = p.value
            if isinstance(val, bool):
                p_info["value"] = val
            elif isinstance(val, (int, float)):
                p_info["value"] = val
            elif val is not None:
                p_info["value"] = str(val)
        except Exception as e:
            p_info["valueError"] = str(e)
        try:
            p_info["units"] = p.units
        except Exception:
            pass
        props.append(p_info)
    return props


# ──────────────────────────────────────────────────────────────────────
# Writable parameter mappings
# ──────────────────────────────────────────────────────────────────────

# Operation parameters that are safe to write (feeds, speeds, engagement).
# Tool geometry is excluded -- those belong to the tool definition.
WRITABLE_OPERATION_PARAMS = {}
WRITABLE_OPERATION_PARAMS.update(FEED_PARAMS)
WRITABLE_OPERATION_PARAMS.update(SPEED_PARAMS)
WRITABLE_OPERATION_PARAMS.update(ENGAGEMENT_PARAMS)

# Machine-level setup parameters that are safe to update.
# Note: Spindle speed and feed rate limits are NOT setup parameters.
# Use SPINDLE_WRITABLE_PARAMS + _write_machine_spindle() for those.
MACHINE_WRITABLE_PARAMS = {
    "machine_dimension_x":         "Machine Dimension X",
    "machine_dimension_y":         "Machine Dimension Y",
    "machine_dimension_z":         "Machine Dimension Z",
    "machineMaxTilt":              "Max Tilt Angle",
}


# ──────────────────────────────────────────────────────────────────────
# Active-command guard (prevents writes while an edit dialog is open)
# ──────────────────────────────────────────────────────────────────────

def _check_no_active_command():
    """Check that no edit dialog / command is active in Fusion 360.

    When an edit dialog is open (e.g. the user double-clicked an operation
    to edit it), Fusion wraps everything in that dialog's undo transaction.
    If the user later cancels the dialog, Fusion rolls back the entire
    transaction -- including any changes the MCP made via the API.

    This guard detects the situation and returns a clear error so the MCP
    can refuse to write and advise the user to close the dialog first.

    Returns:
        None if safe to proceed, or an error dict if a dialog is active.
    """
    try:
        app = adsk.core.Application.get()
        active_cmd = app.userInterface.activeCommand
        if active_cmd and active_cmd != "SelectCommand":
            return {
                "success": False,
                "error": (
                    f"An edit dialog is currently open in Fusion 360 "
                    f"(active command: '{active_cmd}'). "
                    f"Please OK or Cancel the dialog before making changes "
                    f"via MCP. Any API changes made while a dialog is open "
                    f"will be lost if the dialog is cancelled."
                ),
            }
    except Exception:
        pass  # If we cannot determine the state, allow the write to proceed
    return None


# ──────────────────────────────────────────────────────────────────────
# Write helper functions
# ──────────────────────────────────────────────────────────────────────

def _capture_param_snapshot(params_obj, param_names):
    """Snapshot current parameter values for before/after comparison.

    Args:
        params_obj: Fusion parameter collection (e.g. op.parameters).
        param_names: Iterable of parameter name strings to capture.

    Returns:
        dict of {param_name: safe_value} for each parameter that exists.
    """
    snapshot = {}
    for name in param_names:
        val = _read_param(params_obj, name)
        if val is not None:
            snapshot[name] = val
    return snapshot


def _write_param(params_obj, name, expression):
    """Set a parameter value by expression string.

    Uses Fusion's expression format (e.g. "750 mm/min", "12000 rpm").

    Args:
        params_obj: Fusion parameter collection (e.g. op.parameters).
        name: Parameter name string.
        expression: New value as an expression string.

    Returns:
        (success: bool, error_message: str or None)
    """
    try:
        param = params_obj.itemByName(name)
        if param is None:
            return False, f"Parameter '{name}' not found"
        param.expression = str(expression)
        return True, None
    except Exception as e:
        return False, f"Failed to set '{name}': {e}"


def _build_diff(before_snapshot, after_snapshot, label_map):
    """Build a structured diff from two parameter snapshots.

    Args:
        before_snapshot: dict from _capture_param_snapshot (before changes).
        after_snapshot: dict from _capture_param_snapshot (after changes).
        label_map: dict of {param_name: human_label}.

    Returns:
        list of {parameter, label, before, after} dicts.
    """
    changes = []
    all_keys = set(before_snapshot.keys()) | set(after_snapshot.keys())
    for key in sorted(all_keys):
        before_val = before_snapshot.get(key)
        after_val = after_snapshot.get(key)
        if before_val != after_val:
            changes.append({
                "parameter": key,
                "label": label_map.get(key, key),
                "before": before_val,
                "after": after_val,
            })
    return changes


def _find_body_by_name(document_name=None, body_name=None, setup_name=None):
    """Find a BRepBody by name, optionally scoped to a setup.

    Searches setup model bodies first (if setup_name given), then falls
    back to searching all bodies in the root component and sub-components.

    Returns (body, error_dict) tuple.
    """
    if not body_name:
        return None, {"success": False, "error": "Missing required parameter: body_name"}

    # If setup_name is given, search within that setup's models
    if setup_name:
        cam, err = _get_cam(document_name)
        if err:
            return None, err
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return None, err
        models = setup.models
        if models:
            for i in range(models.count):
                body = models.item(i)
                if hasattr(body, "name") and body.name == body_name:
                    return body, None
        return None, {
            "success": False,
            "error": f"Body '{body_name}' not found in setup '{setup_name}'. "
                     f"Use get_setups to see model bodies."
        }

    # No setup specified -- search the design's root component tree
    doc, err = _get_document(document_name)
    if err:
        return None, err
    design = doc.products.itemByProductType("DesignProductType")
    if not design:
        return None, {"success": False, "error": "No Design workspace found in document."}
    design = adsk.fusion.Design.cast(design)
    root = design.rootComponent

    # Search all bodies in root + all occurrences
    def _search_component(comp):
        for i in range(comp.bRepBodies.count):
            body = comp.bRepBodies.item(i)
            if body.name == body_name:
                return body
        return None

    found = _search_component(root)
    if found:
        return found, None

    for i in range(root.allOccurrences.count):
        occ = root.allOccurrences.item(i)
        found = _search_component(occ.component)
        if found:
            return found, None

    return None, {
        "success": False,
        "error": f"Body '{body_name}' not found in document. "
                 f"Use get_setups to see available model bodies."
    }
