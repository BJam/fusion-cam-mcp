# ──────────────────────────────────────────────────────────────────────
# Query: update_setup_machine_params
# Updates machine-level parameters on a CAM setup.
#
# Supports two kinds of parameters:
#   1. Setup parameters (machine dimensions, tilt) -- written via
#      setup.parameters with expression strings like "203 mm".
#   2. Spindle parameters (maxSpindleSpeed, minSpindleSpeed, etc.) --
#      written directly on the MachineSpindle object in the kinematics
#      tree.  Values are plain numbers (RPM, kW, Nm).
#
# Params:
#   setup_name (required)    - Name of the setup to update
#   document_name (optional) - Document to target
#   parameters (required)    - Dict of {param_name: value}
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

    setup_name = params.get("setup_name")
    if not setup_name:
        return {"success": False, "error": "Missing required parameter: setup_name"}

    updates = params.get("parameters")
    if not updates or not isinstance(updates, dict):
        all_params = dict(MACHINE_WRITABLE_PARAMS)
        all_params.update(SPINDLE_WRITABLE_PARAMS)
        return {
            "success": False,
            "error": "Missing or invalid 'parameters' dict. "
                     "Provide a dict of {param_name: value}.",
            "writableParams": all_params,
        }

    setup, err = _find_setup_by_name(cam, setup_name)
    if err:
        return err

    setup_params = setup.parameters
    warnings = []

    machine_desc = "unknown"
    machine_obj = None
    try:
        machine_obj = setup.machine
        if machine_obj:
            machine_desc = (
                f"{machine_obj.vendor} {machine_obj.model}"
                if machine_obj.vendor
                else (machine_obj.description or "unknown")
            )
    except Exception:
        pass

    # Split updates into setup-param writes vs spindle writes
    setup_updates = {}
    spindle_updates = {}
    for pname, pval in updates.items():
        if pname in MACHINE_WRITABLE_PARAMS:
            setup_updates[pname] = pval
        elif pname in SPINDLE_WRITABLE_PARAMS:
            spindle_updates[pname] = pval
        else:
            all_writable = sorted(
                list(MACHINE_WRITABLE_PARAMS.keys())
                + list(SPINDLE_WRITABLE_PARAMS.keys())
            )
            warnings.append(
                f"Parameter '{pname}' is not a writable machine parameter -- skipped. "
                f"Writable params: {all_writable}"
            )

    if not setup_updates and not spindle_updates:
        return {
            "success": False,
            "error": "No valid writable machine parameters provided.",
            "warnings": warnings,
        }

    changes = []
    applied = 0
    skipped = 0

    # ── Handle setup-parameter writes ──
    if setup_updates:
        before = _capture_param_snapshot(setup_params, setup_updates.keys())
        for pname, expression in setup_updates.items():
            ok, err_msg = _write_param(setup_params, pname, expression)
            if ok:
                applied += 1
            else:
                skipped += 1
                warnings.append(err_msg or f"Failed to write '{pname}'")
        adsk.doEvents()
        after = _capture_param_snapshot(setup_params, setup_updates.keys())
        changes.extend(_build_diff(before, after, MACHINE_WRITABLE_PARAMS))

    # ── Handle spindle writes ──
    if spindle_updates:
        if not machine_obj:
            skipped += len(spindle_updates)
            warnings.append("No machine assigned to this setup; cannot update spindle.")
        else:
            spindle_before = _read_machine_spindle(machine_obj) or {}
            for pname, value in spindle_updates.items():
                ok, err_msg = _write_machine_spindle(machine_obj, pname, value)
                if ok:
                    applied += 1
                else:
                    skipped += 1
                    warnings.append(err_msg or f"Failed to write spindle '{pname}'")

            adsk.doEvents()

            spindle_after = _read_machine_spindle(machine_obj) or {}
            for pname in spindle_updates:
                bval = spindle_before.get(pname)
                aval = spindle_after.get(pname)
                if bval != aval:
                    changes.append({
                        "parameter": pname,
                        "label": SPINDLE_WRITABLE_PARAMS.get(pname, pname),
                        "before": bval,
                        "after": aval,
                    })

    result = {
        "target": setup_name,
        "targetType": "setup",
        "machine": machine_desc,
        "changes": changes,
        "changesApplied": applied,
        "changesSkipped": skipped,
    }
    if warnings:
        result["warnings"] = warnings

    return result
