# ──────────────────────────────────────────────────────────────────────
# Operation summary, folder map, material properties, and misc helpers.
#
# Depends on: _1_base.py (constants, _safe_attr, _safe_iter),
#             _2_params.py (_read_param),
#             _5_tools.py (_get_tool_info, _get_coolant_info)
# ──────────────────────────────────────────────────────────────────────

def _get_operation_summary(op):
    """Build a summary dict for an operation."""
    op_params = op.parameters

    parent = _safe_attr(op, "parentSetup")
    op_type = OPERATION_TYPE_MAP.get(
        _safe_attr(parent, "operationType"), None
    ) if parent else None

    summary = {
        "name": op.name,
        "type": op_type,
        "strategy": str(op.strategy) if hasattr(op, "strategy") else None,
        "isSuppressed": op.isSuppressed,
        "hasToolpath": op.hasToolpath,
    }

    notes = _safe_attr(op, "notes")
    if notes:
        summary["notes"] = notes

    tool_info = _get_tool_info(op)
    if tool_info:
        summary["tool"] = tool_info

    coolant = _get_coolant_info(op)
    if coolant:
        summary["coolant"] = coolant

    feeds_speeds = {}
    for key in FEED_PARAMS | SPEED_PARAMS:
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

    if op.hasToolpath:
        valid = _safe_attr(op, "isToolpathValid")
        if valid is not None:
            summary["isToolpathValid"] = valid

    return summary


def _build_folder_map(setup):
    """Walk a setup's child tree and map operation names to folder paths.

    Returns a dict of {operation_name: folder_path} where folder_path is
    the slash-separated path from the setup root (e.g. "Roughing/Walls").
    Operations at the setup root have no entry in the map.
    """
    folder_map = {}

    def _walk(children, path):
        for child in _safe_iter(children):
            child_folder = adsk.cam.CAMFolder.cast(child)
            if child_folder:
                sub_path = f"{path}/{child_folder.name}" if path else child_folder.name
                _walk(_safe_attr(child_folder, "children"), sub_path)
                continue
            child_op = adsk.cam.Operation.cast(child)
            if child_op and path:
                folder_map[child_op.name] = path

    _walk(_safe_attr(setup, "children"), "")
    return folder_map


def _read_all_material_properties(material):
    """Read all physical/mechanical properties from a material object.
    Returns a list of dicts with name, id, value, and units.
    """
    props = []
    for p in _safe_iter(material.materialProperties):
        p_info = {"name": p.name}
        pid = _safe_attr(p, "id")
        if pid:
            p_info["id"] = pid
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
        units = _safe_attr(p, "units")
        if units:
            p_info["units"] = units
        props.append(p_info)
    return props


def _check_no_active_command():
    """Check that no edit dialog / command is active in Fusion 360.

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
        pass
    return None


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
