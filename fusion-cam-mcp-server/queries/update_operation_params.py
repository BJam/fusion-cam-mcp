# ──────────────────────────────────────────────────────────────────────
# Query: update_operation_params
# Updates feeds, speeds, and/or engagement parameters on a CAM operation.
# Returns a before/after diff of all changed values.
#
# Params:
#   operation_name (required) - Name of the operation to update
#   setup_name (optional)     - Setup to search within
#   document_name (optional)  - Document to target
#   parameters (required)     - Dict of {param_name: expression_string}
#                               e.g. {"tool_feedCutting": "750 mm/min",
#                                     "tool_spindleSpeed": "12000 rpm"}
#
# Result: dict with target, changes (before/after), warnings, counts
# ──────────────────────────────────────────────────────────────────────

def run(params):
    dialog_err = _check_no_active_command()
    if dialog_err:
        return dialog_err

    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    operation_name = params.get("operation_name")
    if not operation_name:
        return {"success": False, "error": "Missing required parameter: operation_name"}

    updates = params.get("parameters")
    if not updates or not isinstance(updates, dict):
        return {
            "success": False,
            "error": "Missing or invalid 'parameters' dict. "
                     "Provide a dict of {param_name: expression_string}."
        }

    setup_name = params.get("setup_name")
    op, err = _find_operation_by_name(cam, operation_name, setup_name)
    if err:
        return err

    op_params = op.parameters
    warnings = []

    # Validate parameter names -- only allow known writable params
    valid_updates = {}
    for pname, pval in updates.items():
        if pname in WRITABLE_OPERATION_PARAMS:
            valid_updates[pname] = pval
        else:
            warnings.append(
                f"Parameter '{pname}' is not a writable operation parameter -- skipped. "
                f"Writable params: feeds, speeds, engagement."
            )

    if not valid_updates:
        return {
            "success": False,
            "error": "No valid writable parameters provided.",
            "warnings": warnings,
        }

    # Snapshot BEFORE state for all params we intend to change
    before = _capture_param_snapshot(op_params, valid_updates.keys())

    # Apply changes
    applied = 0
    skipped = 0
    for pname, expression in valid_updates.items():
        ok, err_msg = _write_param(op_params, pname, expression)
        if ok:
            applied += 1
        else:
            skipped += 1
            warnings.append(err_msg)

    adsk.doEvents()

    # Snapshot AFTER state
    after = _capture_param_snapshot(op_params, valid_updates.keys())

    label_map = WRITABLE_OPERATION_PARAMS
    changes = _build_diff(before, after, label_map)

    result = {
        "target": operation_name,
        "targetType": "operation",
        "changes": changes,
        "changesApplied": applied,
        "changesSkipped": skipped,
    }
    if warnings:
        result["warnings"] = warnings

    return result
