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
    for i in range(cam.allOperations.count):
        op = cam.allOperations.item(i)
        if op.isSuppressed:
            continue
        try:
            tool = op.tool
            if not tool:
                continue
            tn = _numval(_read_param_raw(tool.parameters, "tool_number"))
            if tn is not None:
                ops_by_tool_num.setdefault(tn, []).append(op.name)
        except Exception:
            pass

    tools_list = []

    # Primary source: DocumentToolLibrary
    try:
        lib = cam.documentToolLibrary
        if lib:
            for i in range(lib.count):
                tool = lib.item(i)
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

                try:
                    holder = tool.holder
                    if holder:
                        holder_info = {}
                        try:
                            holder_info["description"] = holder.description
                        except Exception:
                            pass
                        if holder_info:
                            info["holder"] = holder_info
                except Exception:
                    pass

                presets = _get_tool_presets(tool)
                if presets:
                    info["presets"] = presets

                tool_num = _numval(info.get("tool_number"))
                used_in = ops_by_tool_num.get(tool_num, [])

                tools_list.append({
                    "tool": info,
                    "usedInOperations": used_in,
                })
    except Exception:
        pass

    # Fallback: if DocumentToolLibrary was empty/unavailable, build from ops
    if not tools_list:
        tools_by_number = {}
        for i in range(cam.allOperations.count):
            op = cam.allOperations.item(i)
            if op.isSuppressed:
                continue
            tool_info = _get_tool_info(op)
            if not tool_info:
                continue
            tool_num = _numval(tool_info.get("tool_number")) or f"unknown_{i}"
            if tool_num not in tools_by_number:
                tools_by_number[tool_num] = {
                    "tool": tool_info,
                    "usedInOperations": [],
                }
            tools_by_number[tool_num]["usedInOperations"].append(op.name)

        for tool_num in sorted(tools_by_number.keys(), key=lambda x: (isinstance(x, str), x)):
            tools_list.append(tools_by_number[tool_num])

    return {"tools": tools_list}
