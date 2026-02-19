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

    for category, param_map in ALL_PARAM_CATEGORIES.items():
        cat_data = {}
        for key, label in param_map.items():
            try:
                p = op_params.itemByName(key)
                if p is None:
                    continue
                val = _safe_param_value(p)
                if val is None:
                    continue
                entry = {"label": label, "value": val}
                try:
                    if not p.isEnabled:
                        entry["isEnabled"] = False
                except Exception:
                    pass
                try:
                    if not p.isEditable:
                        entry["isEditable"] = False
                except Exception:
                    pass
                cat_data[key] = entry
            except Exception:
                pass
        if cat_data:
            all_parameters[category] = cat_data

    # Also read uncategorized parameters, but only visible/enabled ones
    try:
        extra_params = {}
        for i in range(op_params.count):
            param = op_params.item(i)
            name = param.name
            if name in ALL_KNOWN_PARAMS:
                continue
            try:
                if not param.isVisible:
                    continue
            except Exception:
                pass
            val = _safe_param_value(param)
            if val is not None:
                extra_params[name] = val
        if extra_params:
            all_parameters["other"] = extra_params
    except Exception:
        pass

    details["parameters"] = all_parameters

    # Computed metrics for AI analysis
    computed = {}
    try:
        tool_info = details.get("tool", {})
        feeds = details.get("feedsAndSpeeds", {})

        diameter = tool_info.get("tool_diameter")
        flutes = tool_info.get("tool_numberOfFlutes")

        rpm_data = feeds.get("tool_spindleSpeed")
        rpm = rpm_data.get("value") if isinstance(rpm_data, dict) else rpm_data

        feed_data = feeds.get("tool_feedCutting")
        feed = feed_data.get("value") if isinstance(feed_data, dict) else feed_data

        if diameter and rpm:
            surface_speed_cm_per_min = math.pi * diameter * rpm
            computed["surfaceSpeed"] = {
                "value": round(surface_speed_cm_per_min / 100, 2),
                "unit": "m/min",
            }
            computed["surfaceSpeedImperial"] = {
                "value": round(surface_speed_cm_per_min / 100 * 3.28084, 2),
                "unit": "ft/min",
            }

        if feed and rpm and flutes and flutes > 0:
            chip_load_cm = feed / (rpm * flutes)
            computed["chipLoad"] = {
                "value": round(chip_load_cm * 10, 4),
                "unit": "mm",
            }
            computed["chipLoadImperial"] = {
                "value": round(chip_load_cm / 2.54, 5),
                "unit": "in",
            }

        if diameter:
            stepover_data = details.get("engagement", {}).get("stepover")
            if stepover_data:
                stepover = stepover_data.get("value") if isinstance(stepover_data, dict) else stepover_data
                if stepover and diameter > 0:
                    computed["stepoverRatio"] = round(stepover / diameter, 3)

    except Exception:
        pass

    if computed:
        details["computed"] = computed

    return details
