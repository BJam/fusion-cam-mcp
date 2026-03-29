# ──────────────────────────────────────────────────────────────────────
# Query: get_toolpath_status
# Returns toolpath generation status for all operations.
#
# Params: setup_name (optional), document_name (optional)
# Result: {summary: {...}, operations: [...]}
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
        operations = setup.allOperations
    else:
        operations = cam.allOperations

    statuses = []
    for op in _safe_iter(operations):
        status = {
            "name": op.name,
            "isSuppressed": op.isSuppressed,
            "hasToolpath": op.hasToolpath,
        }

        if op.hasToolpath:
            valid = _safe_attr(op, "isToolpathValid")
            if valid is not None:
                status["isToolpathValid"] = valid

        gen_state = _safe_attr(op, "generationStatus")
        if gen_state is not None:
            status["generationStatus"] = str(gen_state)

        warning = _safe_attr(op, "warning")
        if warning:
            status["warning"] = warning

        statuses.append(status)

    summary = {
        "total": len(statuses),
        "withToolpath": sum(1 for s in statuses if s.get("hasToolpath")),
        "valid": sum(1 for s in statuses if s.get("isToolpathValid")),
        "suppressed": sum(1 for s in statuses if s.get("isSuppressed")),
    }

    return {
        "summary": summary,
        "operations": statuses,
    }
