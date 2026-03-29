# ──────────────────────────────────────────────────────────────────────
# Query: get_nc_programs
# Returns all NC programs configured in the document, including their
# associated operations, post-processor, and output settings.
#
# Params: document_name (optional)
# Result: {ncPrograms: [...]}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    nc_progs = _safe_attr(cam, "ncPrograms")
    if not nc_progs:
        return {"ncPrograms": [], "count": 0}

    programs = []
    for nc in _safe_iter(nc_progs):
        entry = {
            "name": nc.name,
            "isSuppressed": nc.isSuppressed,
        }

        notes = _safe_attr(nc, "notes")
        if notes:
            entry["notes"] = notes

        ops = _safe_attr(nc, "operations")
        if ops:
            entry["operations"] = [op.name for op in _safe_iter(ops)]
            entry["operationCount"] = ops.count

        post_config = _safe_attr(nc, "postConfiguration")
        if post_config:
            post_info = {
                k: v for k, v in {
                    "name": _safe_attr(post_config, "name"),
                    "description": _safe_attr(post_config, "description"),
                }.items() if v is not None
            }
            url_obj = _safe_attr(post_config, "postURL")
            if url_obj:
                url_str = _safe_attr(url_obj, "toString")
                if callable(url_str):
                    try:
                        post_info["url"] = url_str()
                    except Exception:
                        pass
            if post_info:
                entry["postConfiguration"] = post_info

        nc_params = _safe_attr(nc, "parameters")
        if nc_params:
            settings = {}
            for pname in [
                "nc_program_filename",
                "nc_program_openInEditor",
                "nc_program_number",
            ]:
                val = _read_param(nc_params, pname)
                if val is not None:
                    settings[pname] = val
            if settings:
                entry["settings"] = settings

        programs.append(entry)

    return {"ncPrograms": programs, "count": len(programs)}
