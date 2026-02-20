# ──────────────────────────────────────────────────────────────────────
# Query: assign_body_material
# Assigns an existing material from a library to a body.
# Returns a before/after diff of the material assignment.
#
# Params:
#   body_name (required)     - Name of the body
#   material_name (required) - Name of the material to assign
#   library_name (required)  - Name of the material library
#   setup_name (optional)    - Setup to search for the body within
#   document_name (optional) - Document to target
#
# Result: dict with body, before/after material info
# ──────────────────────────────────────────────────────────────────────

def _material_snapshot(body):
    """Capture current material info from a body."""
    info = {"material": None, "library": None}
    mat = _safe_attr(body, "material")
    if mat:
        info["material"] = _safe_attr(mat, "name")
        mat_lib = _safe_attr(mat, "materialLibrary")
        if mat_lib:
            info["library"] = _safe_attr(mat_lib, "name")
    return info


def run(params):
    dialog_err = _check_no_active_command()
    if dialog_err:
        return dialog_err

    body_name = params.get("body_name")
    material_name = params.get("material_name")
    library_name = params.get("library_name")
    document_name = params.get("document_name")
    setup_name = params.get("setup_name")

    if not body_name:
        return {"success": False, "error": "Missing required parameter: body_name"}
    if not material_name:
        return {"success": False, "error": "Missing required parameter: material_name"}
    if not library_name:
        return {"success": False, "error": "Missing required parameter: library_name"}

    target_mat, err = _find_material_in_library(library_name, material_name)
    if err:
        return err

    body, err = _find_body_by_name(document_name, body_name, setup_name)
    if err:
        return err

    before_info = _material_snapshot(body)

    try:
        body.material = target_mat
        adsk.doEvents()

        return {
            "target": body_name,
            "targetType": "body",
            "changes": [{
                "parameter": "material",
                "label": "Physical Material",
                "before": before_info,
                "after": _material_snapshot(body),
            }],
            "changesApplied": 1,
            "changesSkipped": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to assign material '{material_name}' "
                     f"to body '{body_name}': {e}"
        }
