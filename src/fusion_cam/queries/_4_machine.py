# ──────────────────────────────────────────────────────────────────────
# Machine spindle access (read/write via kinematics tree).
#
# Depends on: _1_base.py (_safe_attr, _safe_iter, SPINDLE_WRITABLE_PARAMS)
# ──────────────────────────────────────────────────────────────────────

def _find_spindle(machine_obj):
    """Walk machine.kinematics.parts tree and return the first spindle object, or None."""
    kin = _safe_attr(machine_obj, "kinematics")
    if not kin:
        return None
    parts = _safe_attr(kin, "parts")
    if not parts:
        return None

    def _check_part(part):
        sp = _safe_attr(part, "spindle")
        if sp:
            return sp
        for child in _safe_iter(_safe_attr(part, "children")):
            found = _check_part(child)
            if found:
                return found
        return None

    for part in _safe_iter(parts):
        found = _check_part(part)
        if found:
            return found
    return None


def _read_machine_spindle(machine_obj):
    """Read spindle data from machine.kinematics.parts tree.

    Returns a dict with maxSpeed, minSpeed, power, peakTorque,
    peakTorqueSpeed, and description, or None if no spindle is found.
    """
    sp = _find_spindle(machine_obj)
    if not sp:
        return None

    data = {}
    for attr, label, unit in [
        ("maxSpeed", "maxSpindleSpeed", "rpm"),
        ("minSpeed", "minSpindleSpeed", "rpm"),
        ("power", "spindlePower", "kW"),
        ("peakTorque", "peakTorque", "Nm"),
        ("peakTorqueSpeed", "peakTorqueSpeed", "rpm"),
    ]:
        val = _safe_attr(sp, attr)
        if val is not None:
            data[label] = {"value": val, "unit": unit}

    desc = _safe_attr(sp, "description")
    if desc:
        data["description"] = desc

    return data if data else None


def _write_machine_spindle(machine_obj, param_name, value):
    """Write a spindle parameter on the machine's kinematics tree.

    Supported param_name values:
        maxSpindleSpeed, minSpindleSpeed, spindlePower,
        peakTorque, peakTorqueSpeed

    Returns:
        (success: bool, error_message: str or None)
    """
    _SPINDLE_PARAM_MAP = {
        "maxSpindleSpeed": "maxSpeed",
        "minSpindleSpeed": "minSpeed",
        "spindlePower": "power",
        "peakTorque": "peakTorque",
        "peakTorqueSpeed": "peakTorqueSpeed",
    }
    attr_name = _SPINDLE_PARAM_MAP.get(param_name)
    if not attr_name:
        return False, f"Unknown spindle parameter '{param_name}'. Valid: {sorted(_SPINDLE_PARAM_MAP.keys())}"

    spindle = _find_spindle(machine_obj)
    if not spindle:
        return False, "No spindle found in machine kinematics tree"

    try:
        setattr(spindle, attr_name, float(value))
        return True, None
    except Exception as e:
        return False, f"Failed to set spindle.{attr_name}: {e}"
