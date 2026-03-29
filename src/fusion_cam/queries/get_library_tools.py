# ──────────────────────────────────────────────────────────────────────
# Query: get_library_tools
# Reads cutting tools from Fusion 360's CAMLibraryManager — giving
# access to the "Local", "Fusion 360", "Cloud", and "Hub" tool
# libraries that live outside the active document.
#
# This is distinct from get_tools (which reads the DocumentToolLibrary
# embedded in the current file). Use this query to browse the full
# physical tool inventory so an AI can suggest better tool choices.
#
# Params:
#   location      - which library root to query:
#                     "local"   (default) → your machine's local library
#                     "fusion360"         → Autodesk-supplied sample libs
#                     "cloud"             → Autodesk cloud library
#                     "hub"               → team hub library
#   library_name  - optional substring filter on the library filename
#                   (e.g. "Metric", "Inch", "My Library")
#   tool_type     - optional substring filter on tool_type param value
#                   (e.g. "flat end mill", "ball end mill", "drill")
#   min_diameter  - optional minimum tool_diameter filter (cm, Fusion units)
#   max_diameter  - optional maximum tool_diameter filter (cm, Fusion units)
#
# Result: {
#   "location": <str>,
#   "libraries": [
#     { "name": <str>, "url": <str>,
#       "tools": [ { tool fields … } ] }
#   ],
#   "total_tools": <int>
# }
# ──────────────────────────────────────────────────────────────────────

_LOCATION_MAP = {
    "local":     adsk.cam.LibraryLocations.LocalLibraryLocation,
    "fusion360": adsk.cam.LibraryLocations.Fusion360LibraryLocation,
    "cloud":     adsk.cam.LibraryLocations.CloudLibraryLocation,
    "hub":       adsk.cam.LibraryLocations.HubLibraryLocation,
}


def _collect_library_urls(tool_libraries, root_url):
    """Recursively collect all .json tool library asset URLs under root_url."""
    urls = []
    try:
        for asset_url in (tool_libraries.childAssetURLs(root_url) or []):
            urls.append(asset_url.toString())
        for folder_url in (tool_libraries.childFolderURLs(root_url) or []):
            urls.extend(_collect_library_urls(tool_libraries, folder_url))
    except Exception:
        pass
    return urls


def _extract_tool_record(tool, min_dia, max_dia, tool_type_filter):
    """Read geometry params from a Tool object and apply optional filters.
    Returns a dict or None if the tool is filtered out.
    """
    info = {}
    try:
        params = tool.parameters
        for key in TOOL_GEOM_PARAMS:
            val = _read_param(params, key)
            if val is not None:
                info[key] = val

        type_name = _safe_attr(tool, "type")
        if type_name is not None:
            info["tool_typeName"] = str(type_name)

        # tool_type filter
        if tool_type_filter:
            raw_type = info.get("tool_typeName", "")
            if not raw_type:
                # fall back to the parameter value
                tv = _read_param(params, "tool_type")
                raw_type = str(tv.get("value", "")) if isinstance(tv, dict) else str(tv or "")
            if tool_type_filter.lower() not in raw_type.lower():
                return None

        # diameter filters (Fusion stores diameters in cm)
        dia_raw = info.get("tool_diameter")
        if dia_raw is not None:
            dia_val = dia_raw.get("value") if isinstance(dia_raw, dict) else dia_raw
            try:
                dia_float = float(dia_val)
                if min_dia is not None and dia_float < min_dia:
                    return None
                if max_dia is not None and dia_float > max_dia:
                    return None
            except (TypeError, ValueError):
                pass

        # holder
        holder = _safe_attr(tool, "holder")
        if holder:
            holder_info = {}
            desc = _safe_attr(holder, "description")
            if desc:
                holder_info["description"] = desc
            if holder_info:
                info["holder"] = holder_info

        # presets
        presets = _get_tool_presets(tool)
        if presets:
            info["presets"] = presets

    except Exception:
        pass

    return info or None


def run(params):
    location_key = (params.get("location") or "local").lower().strip()
    library_name_filter = (params.get("library_name") or "").strip()
    tool_type_filter = (params.get("tool_type") or "").strip()
    min_diameter = params.get("min_diameter")   # cm
    max_diameter = params.get("max_diameter")   # cm

    location_enum = _LOCATION_MAP.get(location_key)
    if location_enum is None:
        return {
            "error": f"Unknown location '{location_key}'. "
                     f"Valid values: {sorted(_LOCATION_MAP.keys())}"
        }

    try:
        cam_manager = adsk.cam.CAMManager.get()
        lib_manager = cam_manager.libraryManager
        tool_libraries = lib_manager.toolLibraries
    except Exception as exc:
        return {"error": f"Failed to access CAMLibraryManager: {exc}"}

    try:
        root_url = tool_libraries.urlByLocation(location_enum)
    except Exception as exc:
        return {"error": f"Failed to get root URL for location '{location_key}': {exc}"}

    lib_urls = _collect_library_urls(tool_libraries, root_url)

    result_libraries = []
    total_tools = 0

    for url_str in lib_urls:
        # optional library name filter
        if library_name_filter and library_name_filter.lower() not in url_str.lower():
            continue

        try:
            url_obj = adsk.core.URL.create(url_str)
            tool_lib = tool_libraries.toolLibraryAtURL(url_obj)
        except Exception:
            continue

        if not tool_lib:
            continue

        # derive a human-readable name from the URL (last path component minus extension)
        lib_display = url_str.split("/")[-1].replace(".json", "").replace(".hsmlib", "")

        tools_out = []
        try:
            for tool in tool_lib:
                record = _extract_tool_record(tool, min_diameter, max_diameter, tool_type_filter)
                if record is not None:
                    tools_out.append(record)
        except Exception:
            pass

        if tools_out:
            result_libraries.append({
                "name": lib_display,
                "url": url_str,
                "tools": tools_out,
            })
            total_tools += len(tools_out)

    return {
        "location": location_key,
        "libraries": result_libraries,
        "total_tools": total_tools,
    }
