# ──────────────────────────────────────────────────────────────────────
# Query: create_custom_material
# Creates a new material by copying an existing one and overriding
# physical/mechanical properties. The material is added to the design's
# local materials (Fusion API limitation: can't add directly to libraries).
# Optionally assigns the new material to bodies so it shows up in the
# Material Browser under "In This Design".
#
# Params:
#   new_material_name (required)    - Name for the new material
#   source_material_name (required) - Material to copy from
#   source_library_name (required)  - Library containing the source
#   property_overrides (optional)   - Dict of {prop_name: new_value}
#   assign_to_bodies (optional)     - List of body names to assign to
#   document_name (optional)        - Document to target
#
# Result: dict with new material name and all its properties
# ──────────────────────────────────────────────────────────────────────

def run(params):
    dialog_err = _check_no_active_command()
    if dialog_err:
        return dialog_err

    new_material_name = params.get("new_material_name")
    source_material_name = params.get("source_material_name")
    source_library_name = params.get("source_library_name")
    property_overrides = params.get("property_overrides", {})
    assign_to_bodies = params.get("assign_to_bodies", [])
    document_name = params.get("document_name")

    if not new_material_name:
        return {"success": False, "error": "Missing required parameter: new_material_name"}
    if not source_material_name:
        return {"success": False, "error": "Missing required parameter: source_material_name"}
    if not source_library_name:
        return {"success": False, "error": "Missing required parameter: source_library_name"}

    source_mat, err = _find_material_in_library(source_library_name, source_material_name)
    if err:
        return err

    # Get the design for material operations
    doc, err = _get_document(document_name)
    if err:
        return err

    design = doc.products.itemByProductType("DesignProductType")
    if not design:
        return {"success": False, "error": "No Design workspace found"}
    design = adsk.fusion.Design.cast(design)

    # Check if material already exists in design
    new_mat = None
    target_location = None
    errors_list = []

    try:
        existing = design.materials.itemByName(new_material_name)
        if existing:
            new_mat = existing
            target_location = "Design (existing)"
    except Exception:
        pass

    if new_mat is None:
        app = adsk.core.Application.get()
        new_mat, target_location, errors_list = _try_create_material(
            app.materialLibraries, source_mat, new_material_name, design
        )

    if new_mat is None:
        return {
            "success": False,
            "error": f"Failed to create material in any library. "
                     f"Errors: {'; '.join(errors_list)}"
        }

    # Apply property overrides
    changes = []
    prop_errors = []
    mat_props = new_mat.materialProperties
    for prop_name, new_value in property_overrides.items():
        try:
            prop = None
            try:
                prop = mat_props.itemById(prop_name)
            except Exception:
                pass
            if prop is None:
                try:
                    prop = mat_props.itemByName(prop_name)
                except Exception:
                    pass
            if prop is None:
                prop_errors.append(f"Property '{prop_name}' not found")
                continue

            old_val = None
            try:
                old_val = prop.value
            except Exception:
                pass

            prop.value = new_value
            changes.append({
                "property": prop_name,
                "before": old_val,
                "after": new_value,
            })
        except Exception as e:
            prop_errors.append(f"Failed to set '{prop_name}': {e}")

    adsk.doEvents()

    final_props = _read_all_material_properties(new_mat)

    # Assign to bodies if requested
    body_assignments = []
    body_assign_errors = []
    if assign_to_bodies:
        for bname in assign_to_bodies:
            try:
                body, berr = _find_body_by_name(document_name, bname)
                if berr:
                    body_assign_errors.append(
                        f"Body '{bname}': {berr.get('error', 'not found')}"
                    )
                    continue
                old_mat_name = None
                try:
                    if body.material:
                        old_mat_name = body.material.name
                except Exception:
                    pass
                body.material = new_mat
                adsk.doEvents()
                body_assignments.append({
                    "body": bname,
                    "previousMaterial": old_mat_name,
                    "newMaterial": new_mat.name,
                })
            except Exception as e:
                body_assign_errors.append(f"Body '{bname}': {e}")

    result = {
        "materialName": new_mat.name,
        "addedTo": target_location,
        "copiedFrom": source_material_name,
        "sourceLibrary": source_library_name,
        "changesApplied": len(changes),
        "changes": changes,
        "properties": final_props,
    }
    if body_assignments:
        result["bodyAssignments"] = body_assignments
    if body_assign_errors:
        result["bodyAssignmentErrors"] = body_assign_errors
    if prop_errors:
        result["propertyErrors"] = prop_errors
    if errors_list:
        result["libraryAttemptErrors"] = errors_list

    return result


def _try_create_material(mat_libs, source_mat, name, design):
    """Try creating a material in Custom Library, Favorites, or Design."""
    errors = []

    for i in range(mat_libs.count):
        if mat_libs.item(i).name == "Custom Library":
            try:
                new_mat = mat_libs.item(i).materials.addByCopy(source_mat, name)
                return new_mat, "Custom Library", errors
            except Exception as e:
                errors.append(f"Custom Library addByCopy: {e}")
            break

    for i in range(mat_libs.count):
        if mat_libs.item(i).name == "Favorites Library":
            try:
                new_mat = mat_libs.item(i).materials.addByCopy(source_mat, name)
                return new_mat, "Favorites Library", errors
            except Exception as e:
                errors.append(f"Favorites Library addByCopy: {e}")
            break

    try:
        new_mat = design.materials.addByCopy(source_mat, name)
        return new_mat, "Design (local)", errors
    except Exception as e:
        errors.append(f"Design addByCopy: {e}")

    return None, None, errors
