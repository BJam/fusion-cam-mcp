# ──────────────────────────────────────────────────────────────────────
# Query: get_operation_details
# Returns full parameter dump for a specific operation.
#
# Params: operation_name (required), setup_name (optional),
#         document_name (optional)
# Result: full operation details dict with parameters and computed metrics
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    operation_name = params.get("operation_name")
    if not operation_name:
        return {"success": False, "error": "Missing required parameter: operation_name"}

    setup_name = params.get("setup_name")
    op, err = _find_operation_by_name(cam, operation_name, setup_name)
    if err:
        return err

    details = _get_operation_summary(op)

    # Full parameter dump by category
    op_params = op.parameters
    all_parameters = {}

    for category, param_set in ALL_PARAM_CATEGORIES.items():
        cat_data = {}
        for key in param_set:
            try:
                p = op_params.itemByName(key)
                if p is None:
                    continue
                val = _safe_param_value(p)
                if val is None:
                    continue
                entry = {"label": _param_label(p), "value": val}
                enabled = _safe_attr(p, "isEnabled")
                if enabled is not None and not enabled:
                    entry["isEnabled"] = False
                editable = _safe_attr(p, "isEditable")
                if editable is not None and not editable:
                    entry["isEditable"] = False
                cat_data[key] = entry
            except Exception:
                pass
        if cat_data:
            all_parameters[category] = cat_data

    # Auto-categorize parameters not in the explicit sets
    for p in _safe_iter(op_params):
        name = p.name
        if name in ALL_KNOWN_PARAMS:
            continue
        visible = _safe_attr(p, "isVisible")
        if visible is not None and not visible:
            continue
        val = _safe_param_value(p)
        if val is not None:
            cat = _categorize_param(name)
            all_parameters.setdefault(cat, {})[name] = val

    details["parameters"] = all_parameters

    # Computed metrics using UnitsManager.convert() for all unit math.
    computed = {}
    try:
        um = cam.unitsManager

        def _raw(param_set, name):
            """Read raw internal .value from a parameter set."""
            try:
                p = param_set.itemByName(name)
                if p is None:
                    return None
                v = p.value
                return v.value if hasattr(v, "value") else v
            except Exception:
                return None

        tool_obj = op.tool
        diameter_cm = _raw(tool_obj.parameters, "tool_diameter") if tool_obj else None
        flutes = _raw(tool_obj.parameters, "tool_numberOfFlutes") if tool_obj else None
        rpm = _raw(op_params, "tool_spindleSpeed")
        feed_mm_min = _raw(op_params, "tool_feedCutting")

        if diameter_cm and rpm:
            diameter_mm = um.convert(diameter_cm, "cm", "mm")
            ss_m_min = math.pi * diameter_mm * rpm / 1000
            computed["surfaceSpeed"] = {
                "value": round(ss_m_min, 2),
                "unit": "m/min",
            }
            ss_ft_min = um.convert(ss_m_min, "m/min", "ft/min")
            computed["surfaceSpeedImperial"] = {
                "value": round(ss_ft_min, 2),
                "unit": "ft/min",
            }

        if feed_mm_min and rpm and flutes and flutes > 0:
            chip_load_mm = feed_mm_min / (rpm * flutes)
            computed["chipLoad"] = {
                "value": round(chip_load_mm, 4),
                "unit": "mm/tooth",
            }
            chip_load_in = um.convert(chip_load_mm, "mm", "in")
            computed["chipLoadImperial"] = {
                "value": round(chip_load_in, 5),
                "unit": "in/tooth",
            }

        if diameter_cm:
            stepover_cm = _raw(op_params, "stepover")
            if stepover_cm and diameter_cm > 0:
                computed["stepoverRatio"] = round(stepover_cm / diameter_cm, 3)

    except Exception:
        pass

    if computed:
        details["computed"] = computed

    return details
