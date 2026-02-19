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

    programs = []
    try:
        nc_progs = cam.ncPrograms
        if not nc_progs:
            return {"ncPrograms": [], "count": 0}

        for i in range(nc_progs.count):
            nc = nc_progs.item(i)
            entry = {
                "name": nc.name,
                "isSuppressed": nc.isSuppressed,
            }

            try:
                entry["notes"] = nc.notes
            except Exception:
                pass

            # Operations included in this NC program
            try:
                ops = nc.operations
                if ops:
                    entry["operations"] = [ops.item(j).name for j in range(ops.count)]
                    entry["operationCount"] = ops.count
            except Exception:
                pass

            # Post configuration
            try:
                post_config = nc.postConfiguration
                if post_config:
                    post_info = {}
                    try:
                        post_info["name"] = post_config.name
                    except Exception:
                        pass
                    try:
                        post_info["description"] = post_config.description
                    except Exception:
                        pass
                    try:
                        url = post_config.postURL
                        if url:
                            post_info["url"] = url.toString()
                    except Exception:
                        pass
                    if post_info:
                        entry["postConfiguration"] = post_info
            except Exception:
                pass

            # NC program parameters (output settings)
            try:
                nc_params = nc.parameters
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
            except Exception:
                pass

            programs.append(entry)
    except Exception:
        pass

    return {"ncPrograms": programs, "count": len(programs)}
