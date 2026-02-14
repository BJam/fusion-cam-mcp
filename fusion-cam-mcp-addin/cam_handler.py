"""
CAM query handlers for the Fusion 360 CAM MCP add-in.

Each handler reads data from the Fusion 360 CAM API and returns a
JSON-serializable dict. All functions in this module run on the
Fusion main thread (dispatched via CustomEvent from the add-in).
"""

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import math

# ──────────────────────────────────────────────────────────────────────
# CAM parameter name mapping
# ──────────────────────────────────────────────────────────────────────
# These are the known parameter names used by Fusion 360 CAM operations.
# Accessed via operation.parameters.itemByName(key).
# Grouped by category for readability.

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
# These are looked up via itemByName() for speed (no full enumeration).
# Discovered via diagnostic probe of actual Fusion 360 setup.parameters.
_MACHINE_PARAM_NAMES = [
    # Identity (from setup parameters)
    "job_machine",
    "job_machine_manufacturer",
    "job_machine_type",
    "job_machine_configuration",
    "job_machine_configuration_id",
    "job_machine_build_strategy_id",
    # Work envelope
    "machine_dimension_x",
    "machine_dimension_y",
    "machine_dimension_z",
    # Axis limits
    "machineMaxTilt",
]

# Stock-related parameter names to read from setups.
_STOCK_PARAM_NAMES = [
    # Mode
    "job_stockMode",
    # Fixed box dimensions
    "job_stockFixedX",
    "job_stockFixedY",
    "job_stockFixedZ",
    "job_stockFixed_width",
    "job_stockFixed_height",
    "job_stockFixed_depth",
    # Relative offsets
    "job_stockOffsetSide",
    "job_stockOffsetTop",
    "job_stockOffsetBottom",
    # Expand
    "job_stockExpandX",
    "job_stockExpandY",
    "job_stockExpandZ",
    # Other stock params
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
}

ALL_KNOWN_PARAMS = {}
for _cat_params in ALL_PARAM_CATEGORIES.values():
    ALL_KNOWN_PARAMS.update(_cat_params)

# Product type constant
CAM_PRODUCT_TYPE = "CAMProductType"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _get_cam():
    """Get the active CAM product. Returns (cam, error_response) tuple."""
    app = adsk.core.Application.get()
    if not app:
        return None, {"success": False, "error": "Fusion 360 application not available"}

    doc = app.activeDocument
    if not doc:
        return None, {"success": False, "error": "No document is open in Fusion 360"}

    products = doc.products
    cam_product = products.itemByProductType(CAM_PRODUCT_TYPE)
    if not cam_product:
        return None, {"success": False, "error": "No CAM workspace found in the active document. Switch to the Manufacturing workspace first."}

    cam = adsk.cam.CAM.cast(cam_product)
    if not cam:
        return None, {"success": False, "error": "Failed to cast to CAM product"}

    return cam, None


def _safe_param_value(param):
    """Safely extract a parameter value, handling different parameter types.

    Fusion CAM parameters have a .value that returns a typed wrapper object
    (e.g. FloatParameterValue, BooleanParameterValue, ChoiceParameterValue).
    These wrappers have their own .value property containing the actual data.
    """
    if param is None:
        return None
    try:
        expr = None
        try:
            expr = param.expression
        except Exception:
            pass

        val = param.value

        # Unwrap Fusion parameter value objects (FloatParameterValue, etc.)
        # These have a .value property containing the actual number/bool/string
        if hasattr(val, "value"):
            val = val.value

        # Now extract based on the unwrapped type
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


def _get_tool_info(op):
    """Extract tool information from an operation."""
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

        # Also get the tool type as a string
        try:
            info["tool_typeName"] = str(tool.type)
        except Exception:
            pass

        return info
    except Exception:
        return None


def _get_operation_summary(op):
    """Build a summary dict for an operation."""
    params = op.parameters

    summary = {
        "name": op.name,
        "type": str(op.type) if hasattr(op, "type") else None,
        "strategy": str(op.strategy) if hasattr(op, "strategy") else None,
        "isSuppressed": op.isSuppressed,
        "hasToolpath": op.hasToolpath,
    }

    # Tool info
    tool_info = _get_tool_info(op)
    if tool_info:
        summary["tool"] = tool_info

    # Key feeds & speeds
    feeds_speeds = {}
    for key in FEED_PARAMS:
        val = _read_param(params, key)
        if val is not None:
            feeds_speeds[key] = val
    for key in SPEED_PARAMS:
        val = _read_param(params, key)
        if val is not None:
            feeds_speeds[key] = val

    if feeds_speeds:
        summary["feedsAndSpeeds"] = feeds_speeds

    # Key engagement params
    engagement = {}
    for key in ENGAGEMENT_PARAMS:
        val = _read_param(params, key)
        if val is not None:
            engagement[key] = val

    if engagement:
        summary["engagement"] = engagement

    # Toolpath status
    try:
        if op.hasToolpath:
            summary["isToolpathValid"] = op.isToolpathValid
    except Exception:
        pass

    return summary


def _find_setup_by_name(cam, name):
    """Find a setup by name. Returns (setup, error_response) tuple."""
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


# ──────────────────────────────────────────────────────────────────────
# Request handler dispatch
# ──────────────────────────────────────────────────────────────────────

def handle_cam_request(request):
    """
    Dispatch a request to the appropriate handler.
    This runs on the Fusion main thread.
    """
    action = request.get("action", "")
    params = request.get("params", {})

    handlers = {
        "get_document_info":     _handle_get_document_info,
        "get_setups":            _handle_get_setups,
        "get_operations":        _handle_get_operations,
        "get_operation_details": _handle_get_operation_details,
        "get_tools":             _handle_get_tools,
        "get_machining_time":    _handle_get_machining_time,
        "get_toolpath_status":   _handle_get_toolpath_status,
        "ping":                  _handle_ping,
    }

    handler = handlers.get(action)
    if not handler:
        return {
            "success": False,
            "error": f"Unknown action: '{action}'. Available actions: {list(handlers.keys())}"
        }

    try:
        return handler(params)
    except Exception:
        return {
            "success": False,
            "error": f"Error in {action}: {traceback.format_exc()}"
        }


# ──────────────────────────────────────────────────────────────────────
# Handler implementations
# ──────────────────────────────────────────────────────────────────────

def _handle_ping(params):
    """Health check."""
    return {"success": True, "data": {"status": "ok"}}


def _handle_get_document_info(params):
    """Return info about the active document."""
    app = adsk.core.Application.get()
    if not app:
        return {"success": False, "error": "Fusion 360 application not available"}

    doc = app.activeDocument
    if not doc:
        return {"success": False, "error": "No document is open"}

    # Get document units
    design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
    units = "unknown"
    if design:
        units_mgr = design.fusionUnitsManager
        if units_mgr:
            # Fusion internal units are cm, but display units vary
            dist_units = units_mgr.distanceDisplayUnits
            unit_map = {
                0: "mm",
                1: "cm",
                2: "m",
                3: "in",
                4: "ft",
            }
            units = unit_map.get(dist_units, str(dist_units))

    data = {
        "name": doc.name,
        "units": units,
    }

    # Check if CAM is available
    cam_product = doc.products.itemByProductType(CAM_PRODUCT_TYPE)
    data["hasCAM"] = cam_product is not None

    if cam_product:
        cam = adsk.cam.CAM.cast(cam_product)
        data["setupCount"] = cam.setups.count if cam.setups else 0
        data["operationCount"] = cam.allOperations.count if cam.allOperations else 0

    return {"success": True, "data": data}


def _handle_get_setups(params):
    """Return all CAM setups with machine info, stock dimensions, and body materials."""
    cam, err = _get_cam()
    if err:
        return err

    setups = []
    for setup in cam.setups:
        setup_info = {
            "name": setup.name,
            "isSuppressed": setup.isSuppressed,
            "operationCount": setup.allOperations.count,
        }

        # Setup type (milling, turning, etc.)
        try:
            setup_info["type"] = str(setup.operationType)
        except Exception:
            pass

        # ── Machine info from setup.machine object (fast, direct API) ──
        try:
            machine_obj = setup.machine
            if machine_obj:
                machine_info = {}
                # Core identity from the Machine object
                try:
                    machine_info["description"] = machine_obj.description
                except Exception:
                    pass
                try:
                    machine_info["vendor"] = machine_obj.vendor
                except Exception:
                    pass
                try:
                    if machine_obj.model:
                        machine_info["model"] = machine_obj.model
                except Exception:
                    pass
                try:
                    machine_info["id"] = machine_obj.id
                except Exception:
                    pass
                try:
                    if machine_obj.postURL:
                        machine_info["postURL"] = str(machine_obj.postURL)
                except Exception:
                    pass

                if machine_info:
                    setup_info["machine"] = machine_info
        except Exception:
            pass

        # ── Read setup parameters using targeted lookups (fast) ──
        # We use itemByName() instead of iterating all params, because
        # setup.parameters can have hundreds of entries and enumeration
        # is too slow on Fusion's main thread.
        try:
            setup_params = setup.parameters

            # Machine params from setup parameters (work envelope, config)
            machine_params = {}
            for mname in _MACHINE_PARAM_NAMES:
                val = _read_param(setup_params, mname)
                if val is not None and not _is_proxy_str(val):
                    machine_params[mname] = val
            if machine_params:
                # Merge into existing machine info or create new
                if "machine" not in setup_info:
                    setup_info["machine"] = {}
                setup_info["machine"]["parameters"] = machine_params

            # Stock info -- targeted parameter names
            stock_info = {}
            for sname in _STOCK_PARAM_NAMES:
                val = _read_param(setup_params, sname)
                if val is not None and not _is_proxy_str(val):
                    stock_info[sname] = val
            if stock_info:
                setup_info["stock"] = stock_info

            # WCS origin
            try:
                origin = setup_params.itemByName("wcs_origin_boxPoint")
                if origin:
                    val = origin.value
                    if hasattr(val, "value"):
                        val = val.value
                    setup_info["wcsOrigin"] = str(val) if val else None
            except Exception:
                pass

        except Exception:
            pass

        # ── Model bodies with physical materials ──
        try:
            models = setup.models
            if models and models.count > 0:
                model_info = []
                for i in range(models.count):
                    body = models.item(i)
                    body_data = {}

                    if hasattr(body, "name"):
                        body_data["name"] = body.name

                    # Try to get physical material from the body
                    try:
                        mat = body.material
                        if mat:
                            body_data["material"] = mat.name
                            try:
                                body_data["materialLibrary"] = mat.materialLibrary.name
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Fallback: try parent component material
                    if "material" not in body_data:
                        try:
                            if hasattr(body, "parentComponent"):
                                comp = body.parentComponent
                                if comp and comp.material:
                                    body_data["material"] = comp.material.name
                                    try:
                                        body_data["materialLibrary"] = comp.material.materialLibrary.name
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    if body_data:
                        model_info.append(body_data)

                if model_info:
                    setup_info["models"] = model_info
        except Exception:
            pass

        setups.append(setup_info)

    return {"success": True, "data": {"setups": setups}}


def _handle_get_operations(params):
    """Return operations, optionally filtered by setup name."""
    cam, err = _get_cam()
    if err:
        return err

    setup_name = params.get("setup_name")

    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return err
        operations = setup.allOperations
    else:
        operations = cam.allOperations

    ops_data = []
    for i in range(operations.count):
        op = operations.item(i)
        ops_data.append(_get_operation_summary(op))

    return {"success": True, "data": {"operations": ops_data}}


def _handle_get_operation_details(params):
    """Return full parameter dump for a specific operation."""
    cam, err = _get_cam()
    if err:
        return err

    operation_name = params.get("operation_name")
    if not operation_name:
        return {"success": False, "error": "Missing required parameter: operation_name"}

    setup_name = params.get("setup_name")
    op, err = _find_operation_by_name(cam, operation_name, setup_name)
    if err:
        return err

    details = _get_operation_summary(op)

    # Full parameter dump by category
    op_params = op.parameters
    all_parameters = {}

    for category, param_map in ALL_PARAM_CATEGORIES.items():
        cat_data = {}
        for key, label in param_map.items():
            val = _read_param(op_params, key)
            if val is not None:
                cat_data[key] = {"label": label, "value": val}
        if cat_data:
            all_parameters[category] = cat_data

    # Also try to read ALL parameters (including ones not in our mapping)
    try:
        extra_params = {}
        for i in range(op_params.count):
            param = op_params.item(i)
            name = param.name
            if name not in ALL_KNOWN_PARAMS:
                val = _safe_param_value(param)
                if val is not None:
                    extra_params[name] = val
        if extra_params:
            all_parameters["other"] = extra_params
    except Exception:
        pass

    details["parameters"] = all_parameters

    # Computed metrics for AI analysis
    computed = {}
    try:
        tool_info = details.get("tool", {})
        feeds = details.get("feedsAndSpeeds", {})

        diameter = tool_info.get("tool_diameter")
        flutes = tool_info.get("tool_numberOfFlutes")

        # Extract numeric values from feed/speed params
        rpm_data = feeds.get("tool_spindleSpeed")
        rpm = rpm_data.get("value") if isinstance(rpm_data, dict) else rpm_data

        feed_data = feeds.get("tool_feedCutting")
        feed = feed_data.get("value") if isinstance(feed_data, dict) else feed_data

        if diameter and rpm:
            # Surface speed: V = pi * D * RPM (internal units: cm, need to convert)
            # Fusion stores dimensions in cm internally
            surface_speed_cm_per_min = math.pi * diameter * rpm
            computed["surfaceSpeed_m_per_min"] = round(surface_speed_cm_per_min / 100, 2)
            computed["surfaceSpeed_ft_per_min"] = round(surface_speed_cm_per_min / 100 * 3.28084, 2)

        if feed and rpm and flutes and flutes > 0:
            # Chip load: feed / (RPM * flutes)
            # Feed is in cm/min internally
            chip_load_cm = feed / (rpm * flutes)
            computed["chipLoad_mm"] = round(chip_load_cm * 10, 4)
            computed["chipLoad_in"] = round(chip_load_cm / 2.54, 5)

        if diameter:
            stepover_data = details.get("engagement", {}).get("stepover")
            if stepover_data:
                stepover = stepover_data.get("value") if isinstance(stepover_data, dict) else stepover_data
                if stepover and diameter > 0:
                    computed["stepoverRatio"] = round(stepover / diameter, 3)

    except Exception:
        pass

    if computed:
        details["computed"] = computed

    return {"success": True, "data": details}


def _handle_get_tools(params):
    """Return all tools used across operations."""
    cam, err = _get_cam()
    if err:
        return err

    # Collect unique tools by tool number
    tools_by_number = {}
    for i in range(cam.allOperations.count):
        op = cam.allOperations.item(i)
        if op.isSuppressed:
            continue

        tool_info = _get_tool_info(op)
        if not tool_info:
            continue

        tool_num = tool_info.get("tool_number", f"unknown_{i}")
        if tool_num not in tools_by_number:
            tools_by_number[tool_num] = {
                "tool": tool_info,
                "usedInOperations": []
            }

        tools_by_number[tool_num]["usedInOperations"].append(op.name)

    tools_list = []
    for tool_num in sorted(tools_by_number.keys(), key=lambda x: (isinstance(x, str), x)):
        entry = tools_by_number[tool_num]
        entry["tool"]["tool_number"] = tool_num
        tools_list.append(entry)

    return {"success": True, "data": {"tools": tools_list}}


def _handle_get_machining_time(params):
    """Return estimated machining time for setups/operations."""
    cam, err = _get_cam()
    if err:
        return err

    setup_name = params.get("setup_name")
    results = []

    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return err
        setups_to_check = [setup]
    else:
        setups_to_check = [cam.setups.item(i) for i in range(cam.setups.count)]

    for setup in setups_to_check:
        setup_data = {
            "setupName": setup.name,
            "operations": []
        }

        for i in range(setup.allOperations.count):
            op = setup.allOperations.item(i)
            op_time = {
                "name": op.name,
                "isSuppressed": op.isSuppressed,
                "hasToolpath": op.hasToolpath,
            }

            if op.hasToolpath and not op.isSuppressed:
                try:
                    # getMachiningTime requires:
                    #   operation, feedScale (1.0 = 100%), rapidFeed (cm/min), toolChangeTime (seconds)
                    # Using 1.0 feed scale, 500 cm/min (~200 ipm) rapid, 15s tool change
                    feed_scale = 1.0
                    rapid_feed = 500.0   # cm/min (~200 ipm)
                    tool_change_time = 15.0  # seconds
                    time_result = cam.getMachiningTime(op, feed_scale, rapid_feed, tool_change_time)
                    if time_result:
                        # MachiningTime object - read available properties
                        mach_time = getattr(time_result, "machiningTime", None)
                        if mach_time is not None:
                            op_time["machiningTime_seconds"] = mach_time
                        # Try different property names for rapid/total time
                        for attr_name in ["rapidTime", "rapid_time", "rapidtime"]:
                            rapid = getattr(time_result, attr_name, None)
                            if rapid is not None:
                                op_time["rapidTime_seconds"] = rapid
                                break
                        for attr_name in ["totalTime", "total_time", "totaltime"]:
                            total = getattr(time_result, attr_name, None)
                            if total is not None:
                                op_time["totalTime_seconds"] = total
                                op_time["totalTime_formatted"] = _format_time(total)
                                break
                        # Fallback: use machiningTime as totalTime if no total found
                        if "totalTime_seconds" not in op_time and mach_time is not None:
                            op_time["totalTime_seconds"] = mach_time
                            op_time["totalTime_formatted"] = _format_time(mach_time)
                except Exception as e:
                    op_time["timeError"] = str(e)

            setup_data["operations"].append(op_time)

        # Sum up times for the setup
        total = sum(
            op.get("totalTime_seconds", 0)
            for op in setup_data["operations"]
        )
        setup_data["totalTime_seconds"] = total
        setup_data["totalTime_formatted"] = _format_time(total)

        results.append(setup_data)

    return {"success": True, "data": {"setups": results}}


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


def _handle_get_toolpath_status(params):
    """Return toolpath generation status for all operations."""
    cam, err = _get_cam()
    if err:
        return err

    setup_name = params.get("setup_name")
    statuses = []

    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return err
        operations = setup.allOperations
    else:
        operations = cam.allOperations

    for i in range(operations.count):
        op = operations.item(i)
        status = {
            "name": op.name,
            "isSuppressed": op.isSuppressed,
            "hasToolpath": op.hasToolpath,
        }

        if op.hasToolpath:
            try:
                status["isToolpathValid"] = op.isToolpathValid
            except Exception:
                pass

        # Check if toolpath needs regeneration
        try:
            gen_state = op.generationStatus
            status["generationStatus"] = str(gen_state)
        except Exception:
            pass

        # Check for warnings
        try:
            if hasattr(op, "warning") and op.warning:
                status["warning"] = op.warning
        except Exception:
            pass

        statuses.append(status)

    # Summary counts
    summary = {
        "total": len(statuses),
        "withToolpath": sum(1 for s in statuses if s.get("hasToolpath")),
        "valid": sum(1 for s in statuses if s.get("isToolpathValid")),
        "suppressed": sum(1 for s in statuses if s.get("isSuppressed")),
    }

    return {
        "success": True,
        "data": {
            "summary": summary,
            "operations": statuses
        }
    }


