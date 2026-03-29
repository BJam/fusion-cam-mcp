# ──────────────────────────────────────────────────────────────────────
# Query: get_material_properties
# Reads all physical/mechanical properties of a specific material.
# Useful for inspecting existing materials before creating custom ones.
#
# Params:
#   material_name (required)  - Name of the material
#   library_name (required)   - Name of the material library
#   document_name (optional)  - Document to target
#
# Result: dict with material name, library, and all properties
# ──────────────────────────────────────────────────────────────────────

def run(params):
    material_name = params.get("material_name")
    library_name = params.get("library_name")

    if not material_name:
        return {"success": False, "error": "Missing required parameter: material_name"}
    if not library_name:
        return {"success": False, "error": "Missing required parameter: library_name"}

    target_mat, err = _find_material_in_library(library_name, material_name)
    if err:
        return err

    try:
        props_data = _read_all_material_properties(target_mat)
    except Exception as e:
        props_data = [{"error": f"Failed to read properties: {e}"}]

    return {
        "material": material_name,
        "library": library_name,
        "properties": props_data,
    }
