# ──────────────────────────────────────────────────────────────────────
# Query: get_setups
# Returns all CAM setups with machine info, stock dimensions, and
# body materials.
#
# Params: document_name (optional)
# Result: {setups: [...]}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    setups = []
    for setup in cam.setups:
        setup_info = {
            "name": setup.name,
            "isSuppressed": setup.isSuppressed,
            "operationCount": setup.allOperations.count,
        }

        op_type = _safe_attr(setup, "operationType")
        if op_type is not None:
            setup_info["type"] = OPERATION_TYPE_MAP.get(op_type, str(op_type))

        # ── Machine info from setup.machine object ──
        machine_obj = _safe_attr(setup, "machine")
        if machine_obj:
            machine_info = {
                k: v for k, v in {
                    "description": _safe_attr(machine_obj, "description"),
                    "vendor": _safe_attr(machine_obj, "vendor"),
                    "model": _safe_attr(machine_obj, "model"),
                    "id": _safe_attr(machine_obj, "id"),
                }.items() if v is not None
            }

            url_obj = _safe_attr(machine_obj, "postURL")
            if url_obj:
                url_str = _safe_attr(url_obj, "toString")
                if callable(url_str):
                    try:
                        machine_info["postURL"] = url_str()
                    except Exception:
                        pass

            spindle_info = _read_machine_spindle(machine_obj)
            if spindle_info:
                machine_info["spindle"] = spindle_info

            if machine_info:
                setup_info["machine"] = machine_info

        # ── Read setup parameters using targeted lookups ──
        setup_params = _safe_attr(setup, "parameters")
        if setup_params:
            machine_params = {}
            for mname in _MACHINE_PARAM_NAMES:
                val = _read_param(setup_params, mname)
                if val is not None and not _is_proxy_str(val):
                    machine_params[mname] = val

            known_setup_params = set(_MACHINE_PARAM_NAMES) | set(_STOCK_PARAM_NAMES)
            for p in _safe_iter(setup_params):
                name = p.name
                if name.startswith(("job_machine", "machine_")) and name not in known_setup_params:
                    val = _safe_param_value(p)
                    if val is not None and not _is_proxy_str(val):
                        machine_params[name] = val

            if machine_params:
                if "machine" not in setup_info:
                    setup_info["machine"] = {}
                setup_info["machine"]["parameters"] = machine_params

            stock_info = {}
            for sname in _STOCK_PARAM_NAMES:
                val = _read_param(setup_params, sname)
                if val is not None and not _is_proxy_str(val):
                    stock_info[sname] = val
            if stock_info:
                setup_info["stock"] = stock_info

            origin = _read_param(setup_params, "wcs_origin_boxPoint")
            if origin is not None:
                setup_info["wcsOrigin"] = str(origin)

        # ── Model bodies with physical materials ──
        models = _safe_attr(setup, "models")
        if models:
            model_info = []
            for body in _safe_iter(models):
                body_data = {}
                name = _safe_attr(body, "name")
                if name:
                    body_data["name"] = name

                mat = _safe_attr(body, "material")
                if mat:
                    body_data["material"] = _safe_attr(mat, "name")
                    mat_lib = _safe_attr(mat, "materialLibrary")
                    if mat_lib:
                        body_data["materialLibrary"] = _safe_attr(mat_lib, "name")

                if "material" not in body_data:
                    comp = _safe_attr(body, "parentComponent")
                    comp_mat = _safe_attr(comp, "material") if comp else None
                    if comp_mat:
                        body_data["material"] = _safe_attr(comp_mat, "name")
                        comp_mat_lib = _safe_attr(comp_mat, "materialLibrary")
                        if comp_mat_lib:
                            body_data["materialLibrary"] = _safe_attr(comp_mat_lib, "name")

                if body_data:
                    model_info.append(body_data)

            if model_info:
                setup_info["models"] = model_info

        setups.append(setup_info)

    return {"setups": setups}
