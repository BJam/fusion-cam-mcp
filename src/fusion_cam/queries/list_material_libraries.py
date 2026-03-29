# ──────────────────────────────────────────────────────────────────────
# Query: list_material_libraries
# Lists available material libraries and their materials for discovery.
# Used before assign_body_material to find valid library/material names.
#
# Params:
#   library_name (optional)  - Filter to a specific library
#   document_name (optional) - Document to target
#
# Result: dict with libraries list, each containing name and materials
# ──────────────────────────────────────────────────────────────────────

def run(params):
    app = adsk.core.Application.get()
    if not app:
        return {"success": False, "error": "Fusion 360 application not available"}

    library_name = params.get("library_name")
    mat_libs = app.materialLibraries

    if not mat_libs or mat_libs.count == 0:
        return {"success": False, "error": "No material libraries available"}

    libraries = []

    for i in range(mat_libs.count):
        lib = mat_libs.item(i)
        lib_name = lib.name

        if library_name and lib_name != library_name:
            continue

        lib_info = {
            "name": lib_name,
            "materialCount": lib.materials.count,
        }

        materials = []
        for mat in _safe_iter(lib.materials):
            mat_info = {"name": mat.name}
            mat_id = _safe_attr(mat, "id")
            if mat_id:
                mat_info["id"] = mat_id
            materials.append(mat_info)

        lib_info["materials"] = materials
        libraries.append(lib_info)

    if library_name and not libraries:
        available = [mat_libs.item(i).name for i in range(mat_libs.count)]
        return {
            "success": False,
            "error": f"Material library '{library_name}' not found. "
                     f"Available libraries: {available}"
        }

    return {"libraries": libraries}
