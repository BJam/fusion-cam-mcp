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

        try:
            setup_info["type"] = OPERATION_TYPE_MAP.get(
                setup.operationType, str(setup.operationType)
            )
        except Exception:
            pass

        # ── Machine info from setup.machine object ──
        try:
            machine_obj = setup.machine
            if machine_obj:
                machine_info = {}
                try:
                    machine_info["description"] = machine_obj.description
                except Exception:
                    pass
                try:
                    machine_info["vendor"] = machine_obj.vendor
                except Exception:
                    pass
                try:
                    if machine_obj.model:
                        machine_info["model"] = machine_obj.model
                except Exception:
                    pass
                try:
                    machine_info["id"] = machine_obj.id
                except Exception:
                    pass
                try:
                    url_obj = machine_obj.postURL
                    if url_obj:
                        try:
                            machine_info["postURL"] = url_obj.toString()
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    spindle_info = _read_machine_spindle(machine_obj)
                    if spindle_info:
                        machine_info["spindle"] = spindle_info
                except Exception:
                    pass

                if machine_info:
                    setup_info["machine"] = machine_info
        except Exception:
            pass

        # ── Read setup parameters using targeted lookups ──
        try:
            setup_params = setup.parameters

            machine_params = {}
            for mname in _MACHINE_PARAM_NAMES:
                val = _read_param(setup_params, mname)
                if val is not None and not _is_proxy_str(val):
                    machine_params[mname] = val
            if machine_params:
                if "machine" not in setup_info:
                    setup_info["machine"] = {}
                setup_info["machine"]["parameters"] = machine_params

            # Enumerate ALL setup parameters to catch machine params we don't know about
            try:
                known_setup_params = set(_MACHINE_PARAM_NAMES) | set(_STOCK_PARAM_NAMES)
                extra_machine = {}
                for i in range(setup_params.count):
                    p = setup_params.item(i)
                    name = p.name
                    if name.startswith(("job_machine", "machine_")) and name not in known_setup_params:
                        val = _safe_param_value(p)
                        if val is not None and not _is_proxy_str(val):
                            extra_machine[name] = val
                if extra_machine:
                    if "machine" not in setup_info:
                        setup_info["machine"] = {}
                    if "parameters" not in setup_info["machine"]:
                        setup_info["machine"]["parameters"] = {}
                    setup_info["machine"]["parameters"].update(extra_machine)
            except Exception:
                pass

            stock_info = {}
            for sname in _STOCK_PARAM_NAMES:
                val = _read_param(setup_params, sname)
                if val is not None and not _is_proxy_str(val):
                    stock_info[sname] = val
            if stock_info:
                setup_info["stock"] = stock_info

            try:
                origin = setup_params.itemByName("wcs_origin_boxPoint")
                if origin:
                    val = origin.value
                    if hasattr(val, "value"):
                        val = val.value
                    setup_info["wcsOrigin"] = str(val) if val else None
            except Exception:
                pass

        except Exception:
            pass

        # ── Model bodies with physical materials ──
        try:
            models = setup.models
            if models and models.count > 0:
                model_info = []
                for i in range(models.count):
                    body = models.item(i)
                    body_data = {}

                    if hasattr(body, "name"):
                        body_data["name"] = body.name

                    try:
                        mat = body.material
                        if mat:
                            body_data["material"] = mat.name
                            try:
                                body_data["materialLibrary"] = mat.materialLibrary.name
                            except Exception:
                                pass
                    except Exception:
                        pass

                    if "material" not in body_data:
                        try:
                            if hasattr(body, "parentComponent"):
                                comp = body.parentComponent
                                if comp and comp.material:
                                    body_data["material"] = comp.material.name
                                    try:
                                        body_data["materialLibrary"] = comp.material.materialLibrary.name
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    if body_data:
                        model_info.append(body_data)

                if model_info:
                    setup_info["models"] = model_info
        except Exception:
            pass

        setups.append(setup_info)

    return {"setups": setups}
