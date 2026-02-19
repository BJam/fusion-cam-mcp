# ──────────────────────────────────────────────────────────────────────
# Query: get_machining_time
# Returns estimated machining time for setups/operations.
#
# Params: setup_name (optional), document_name (optional),
#         rapid_feed (optional, cm/min), tool_change_time (optional, seconds)
# Result: {setups: [...]}
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
        setups_to_check = [setup]
    else:
        setups_to_check = [cam.setups.item(i) for i in range(cam.setups.count)]

    results = []
    for setup in setups_to_check:
        setup_data = {
            "setupName": setup.name,
            "operations": []
        }

        for i in range(setup.allOperations.count):
            op = setup.allOperations.item(i)
            op_time = {
                "name": op.name,
                "isSuppressed": op.isSuppressed,
                "hasToolpath": op.hasToolpath,
            }

            if op.hasToolpath and not op.isSuppressed:
                try:
                    feed_scale = 1.0
                    rapid_feed = params.get("rapid_feed", DEFAULT_RAPID_FEED)
                    tool_change_time = params.get("tool_change_time", DEFAULT_TOOL_CHANGE_TIME)
                    time_result = cam.getMachiningTime(op, feed_scale, rapid_feed, tool_change_time)
                    if time_result:
                        mach_time = getattr(time_result, "machiningTime", None)
                        if mach_time is not None:
                            op_time["machiningTimeSeconds"] = mach_time
                        for attr_name in ["rapidTime", "rapid_time", "rapidtime"]:
                            rapid = getattr(time_result, attr_name, None)
                            if rapid is not None:
                                op_time["rapidTimeSeconds"] = rapid
                                break
                        for attr_name in ["totalTime", "total_time", "totaltime"]:
                            total = getattr(time_result, attr_name, None)
                            if total is not None:
                                op_time["totalTimeSeconds"] = total
                                op_time["totalTimeFormatted"] = _format_time(total)
                                break
                        if "totalTimeSeconds" not in op_time and mach_time is not None:
                            op_time["totalTimeSeconds"] = mach_time
                            op_time["totalTimeFormatted"] = _format_time(mach_time)
                except Exception as e:
                    op_time["timeError"] = str(e)

            setup_data["operations"].append(op_time)

        total = sum(
            op.get("totalTimeSeconds", 0)
            for op in setup_data["operations"]
        )
        setup_data["totalTimeSeconds"] = total
        setup_data["totalTimeFormatted"] = _format_time(total)

        results.append(setup_data)

    return {"setups": results}
