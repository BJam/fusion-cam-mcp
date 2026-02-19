# ──────────────────────────────────────────────────────────────────────
# Query: generate_toolpaths
# Triggers toolpath generation for specified operations or entire setups.
#
# Params: setup_name (optional), operation_names (optional list),
#         document_name (optional)
# Result: {generated: [...], summary: {...}}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    dialog_err = _check_no_active_command()
    if dialog_err:
        return dialog_err

    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    setup_name = params.get("setup_name")
    operation_names = params.get("operation_names")

    operations_to_generate = []

    if operation_names:
        for op_name in operation_names:
            op, err = _find_operation_by_name(cam, op_name, setup_name)
            if err:
                return err
            operations_to_generate.append(op)
    elif setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return err
        for i in range(setup.allOperations.count):
            op = setup.allOperations.item(i)
            if not op.isSuppressed:
                operations_to_generate.append(op)
    else:
        for i in range(cam.allOperations.count):
            op = cam.allOperations.item(i)
            if not op.isSuppressed:
                operations_to_generate.append(op)

    if not operations_to_generate:
        return {
            "success": False,
            "error": "No operations found to generate toolpaths for. "
                     "Check that operations exist and are not suppressed."
        }

    op_collection = adsk.core.ObjectCollection.create()
    for op in operations_to_generate:
        op_collection.add(op)

    try:
        future = cam.generateToolpath(op_collection)

        import time
        max_wait = 300  # 5 minutes max
        poll_interval = 0.5
        elapsed = 0.0

        while not future.isGenerationCompleted:
            if elapsed >= max_wait:
                break
            time.sleep(poll_interval)
            elapsed += poll_interval
            adsk.doEvents()

        generated = []
        for op in operations_to_generate:
            op_result = {
                "name": op.name,
                "hasToolpath": op.hasToolpath,
            }
            try:
                if op.hasToolpath:
                    op_result["isToolpathValid"] = op.isToolpathValid
            except Exception:
                pass
            generated.append(op_result)

        completed_count = sum(1 for g in generated if g.get("hasToolpath"))
        valid_count = sum(1 for g in generated if g.get("isToolpathValid"))
        timed_out = not future.isGenerationCompleted

        return {
            "generated": generated,
            "summary": {
                "totalOperations": len(generated),
                "withToolpath": completed_count,
                "valid": valid_count,
                "timedOut": timed_out,
                "elapsedSeconds": round(elapsed, 1),
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Toolpath generation failed: {e}"
        }
