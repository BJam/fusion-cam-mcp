# ──────────────────────────────────────────────────────────────────────
# Query: get_tools
# Returns all tools from the document tool library, cross-referenced
# with operations to show where each tool is used.
#
# Params: document_name (optional)
# Result: {tools: [...]}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    # Build operation→tool_number mapping for cross-reference
    ops_by_tool_num = {}
    for op in _safe_iter(cam.allOperations):
        if op.isSuppressed:
            continue
        tool = _safe_attr(op, "tool")
        if not tool:
            continue
        tn = _numval(_read_param(_safe_attr(tool, "parameters"), "tool_number"))
        if tn is not None:
            ops_by_tool_num.setdefault(tn, []).append(op.name)

    tools_list = []

    # Primary source: DocumentToolLibrary -- use _get_tool_info pattern
    lib = _safe_attr(cam, "documentToolLibrary")
    if lib:
        for tool in _safe_iter(lib):
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
                if holder_info:
                    info["holder"] = holder_info

            presets = _get_tool_presets(tool)
            if presets:
                info["presets"] = presets

            tool_num = _numval(info.get("tool_number"))
            used_in = ops_by_tool_num.get(tool_num, [])

            tools_list.append({
                "tool": info,
                "usedInOperations": used_in,
            })

    # Fallback: if DocumentToolLibrary was empty/unavailable, build from ops
    if not tools_list:
        tools_by_number = {}
        for op in _safe_iter(cam.allOperations):
            if op.isSuppressed:
                continue
            tool_info = _get_tool_info(op)
            if not tool_info:
                continue
            tool_num = _numval(tool_info.get("tool_number")) or f"unknown_{op.name}"
            if tool_num not in tools_by_number:
                tools_by_number[tool_num] = {
                    "tool": tool_info,
                    "usedInOperations": [],
                }
            tools_by_number[tool_num]["usedInOperations"].append(op.name)

        for tool_num in sorted(tools_by_number.keys(), key=lambda x: (isinstance(x, str), x)):
            tools_list.append(tools_by_number[tool_num])

    return {"tools": tools_list}
