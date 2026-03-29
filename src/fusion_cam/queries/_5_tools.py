# ──────────────────────────────────────────────────────────────────────
# Tool, preset, and coolant helpers.
#
# Depends on: _1_base.py (param sets, _safe_attr, _safe_iter, _is_proxy_str),
#             _2_params.py (_read_param, _safe_param_value)
# ──────────────────────────────────────────────────────────────────────

def _get_tool_info(op):
    """Extract tool information from an operation, including holder and coolant."""
    tool = _safe_attr(op, "tool")
    if not tool:
        return None

    try:
        tool_params = tool.parameters
        info = {}
        for key in TOOL_GEOM_PARAMS:
            val = _read_param(tool_params, key)
            if val is not None:
                info[key] = val

        type_name = _safe_attr(tool, "type")
        if type_name is not None:
            info["tool_typeName"] = str(type_name)

        holder = _safe_attr(tool, "holder")
        if holder:
            holder_info = {}
            desc = _safe_attr(holder, "description")
            if desc:
                holder_info["description"] = desc
            for p in _safe_iter(_safe_attr(holder, "parameters")):
                val = _safe_param_value(p)
                if val is not None and not _is_proxy_str(str(val)):
                    holder_info[p.name] = val
            if holder_info:
                info["holder"] = holder_info

        presets = _get_tool_presets(tool)
        if presets:
            info["presets"] = presets

        return info
    except Exception:
        return None


def _get_tool_presets(tool):
    """Extract presets (material-specific feeds/speeds) from a Tool object.

    Returns a list of preset dicts, each with name, id, and the feed/speed
    parameters that differ from the base tool settings.
    """
    presets = []
    for preset in _safe_iter(_safe_attr(tool, "presets")):
        entry = {}
        name = _safe_attr(preset, "name")
        if name:
            entry["name"] = name
        pid = _safe_attr(preset, "id")
        if pid:
            entry["id"] = pid

        pp = _safe_attr(preset, "parameters")
        if pp:
            fs = {}
            for key in FEED_PARAMS | SPEED_PARAMS:
                val = _read_param(pp, key)
                if val is not None:
                    fs[key] = val
            if fs:
                entry["feedsAndSpeeds"] = fs

            eng = {}
            for key in ENGAGEMENT_PARAMS:
                val = _read_param(pp, key)
                if val is not None:
                    eng[key] = val
            if eng:
                entry["engagement"] = eng

        if entry:
            presets.append(entry)
    return presets


def _get_coolant_info(op):
    """Extract coolant mode from an operation."""
    def _extract(val):
        if val is None:
            return None
        if isinstance(val, dict):
            return val.get("expression", str(val.get("value")))
        return str(val)

    tool = _safe_attr(op, "tool")
    if tool:
        result = _extract(_read_param(_safe_attr(tool, "parameters"), "tool_coolant"))
        if result:
            return result
    return _extract(_read_param(_safe_attr(op, "parameters"), "tool_coolant"))
