# ──────────────────────────────────────────────────────────────────────
# Query: get_operations
# Returns operations, optionally filtered by setup name.
#
# Params: setup_name (optional), document_name (optional)
# Result: {operations: [...]}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    setup_name = params.get("setup_name")

    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return err
        setups_to_scan = [setup]
        operations = setup.allOperations
    else:
        setups_to_scan = list(cam.setups)
        operations = cam.allOperations

    # Build folder map across all relevant setups
    folder_map = {}
    for s in setups_to_scan:
        folder_map.update(_build_folder_map(s))

    ops_data = []
    for i in range(operations.count):
        op = operations.item(i)
        summary = _get_operation_summary(op)
        folder = folder_map.get(op.name)
        if folder:
            summary["folder"] = folder
        ops_data.append(summary)

    return {"operations": ops_data}
