# ──────────────────────────────────────────────────────────────────────
# Parameter reading, writing, unit conversion, and diff building.
#
# Depends on: _1_base.py (constants, _safe_attr, _is_proxy_str)
# ──────────────────────────────────────────────────────────────────────

# FloatParameterValueTypes enum → internal unit string.
_CAM_INTERNAL_UNITS = {
    1: "cm",         # LengthValueType
    2: "deg",        # AngleValueType (CAM stores degrees)
    3: "mm/min",     # LinearVelocityValueType
    4: "rpm",        # RotationalVelocityValueType
    5: "s",          # TimeValueType
    6: "kg",         # WeightValueType
    7: "W",          # PowerValueType
    8: "l/min",      # FlowRateValueType
    9: "cm*cm",      # AreaValueType
    10: "cm*cm*cm",  # VolumeValueType
    11: "C",         # TemperatureValueType
}

# FloatParameterValueTypes enum → (metric_display_unit, imperial_display_unit)
_CAM_DISPLAY_UNITS = {
    1: ("mm", "in"),
    2: ("deg", "deg"),
    3: ("mm/min", "in/min"),
    4: ("rpm", "rpm"),
    5: ("s", "s"),
    6: ("kg", "lb"),
    7: ("W", "W"),
    8: ("l/min", "l/min"),
    9: ("mm*mm", "in*in"),
    10: ("mm*mm*mm", "in*in*in"),
    11: ("C", "C"),
}

_um_cache = {}
_imperial_cache = {}


def _get_document_units(doc):
    """Get display units for a document as a short string (mm, in, etc.)."""
    try:
        design = adsk.fusion.Design.cast(
            doc.products.itemByProductType("DesignProductType")
        )
        if design and design.fusionUnitsManager:
            dist_units = design.fusionUnitsManager.distanceDisplayUnits
            return DISTANCE_UNIT_MAP.get(dist_units, str(dist_units))
    except Exception:
        pass
    return "unknown"


def _get_units_manager():
    """Get the active document's UnitsManager, cached per query execution."""
    try:
        app = adsk.core.Application.get()
        doc = app.activeDocument
        doc_id = id(doc)
        if doc_id not in _um_cache:
            um = None
            design = adsk.fusion.Design.cast(
                doc.products.itemByProductType("DesignProductType")
            )
            if design:
                um = design.unitsManager
            else:
                cam = adsk.cam.CAM.cast(
                    doc.products.itemByProductType(CAM_PRODUCT_TYPE)
                )
                if cam:
                    um = cam.unitsManager
            _um_cache[doc_id] = um
        return _um_cache.get(doc_id)
    except Exception:
        return None


def _is_imperial():
    """Check if the active document uses imperial distance units, cached."""
    try:
        app = adsk.core.Application.get()
        doc = app.activeDocument
        doc_id = id(doc)
        if doc_id not in _imperial_cache:
            _imperial_cache[doc_id] = _get_document_units(doc) in ("in", "ft")
        return _imperial_cache[doc_id]
    except Exception:
        return False


def _param_label(param):
    """Get a human-readable label from a CAMParameter via its .title property.

    Falls back to param.name if .title is unavailable. The Fusion API
    provides .title / .fullTitle on CAMParameter objects, so we get
    labels for free without maintaining manual name-to-label maps.
    """
    title = _safe_attr(param, "title")
    if title:
        return title
    return _safe_attr(param, "name") or "unknown"


def _safe_param_value(param):
    """Safely extract a parameter value with display-unit conversion.

    Uses FloatParameterValue.type to determine the internal unit, then
    UnitsManager.convert() to produce the display-unit value.

    Returns:
      - For floats: {"value": display_number, "unit": "mm", "expression": "..."}
      - For bools: True/False
      - For strings: the string value
      - None on failure
    """
    if param is None:
        return None
    try:
        expr = None
        try:
            expr = param.expression
        except Exception:
            pass

        val_obj = param.value

        float_val = adsk.cam.FloatParameterValue.cast(val_obj)
        if float_val is not None:
            raw = float_val.value
            if isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)):
                return str(raw)
            val_type = float_val.type
            internal_unit = _CAM_INTERNAL_UNITS.get(val_type)
            display_pair = _CAM_DISPLAY_UNITS.get(val_type)
            if internal_unit and display_pair:
                target = display_pair[1] if _is_imperial() else display_pair[0]
                um = _get_units_manager()
                if um:
                    display_val = um.convert(raw, internal_unit, target)
                    if display_val != -1:
                        return {"value": round(display_val, 6), "unit": target, "expression": expr}
                # Conversion failed; use internal unit as fallback
                return {"value": raw, "unit": internal_unit, "expression": expr}
            return {"value": raw, "unit": None, "expression": expr}

        if hasattr(val_obj, "value"):
            val_obj = val_obj.value

        if isinstance(val_obj, bool):
            return val_obj
        elif isinstance(val_obj, (int, float)):
            if isinstance(val_obj, float) and (math.isnan(val_obj) or math.isinf(val_obj)):
                return str(val_obj)
            return {"value": val_obj, "unit": None, "expression": expr if expr else str(val_obj)}
        elif isinstance(val_obj, str):
            return val_obj
        else:
            return str(val_obj) if val_obj is not None else None
    except Exception:
        try:
            val = param.value
            if hasattr(val, "value"):
                val = val.value
            return str(val) if val is not None else None
        except Exception:
            return None


def _read_param(params, name):
    """Read a single parameter by name, returning None if not found."""
    try:
        param = params.itemByName(name)
        if param is None:
            return None
        return _safe_param_value(param)
    except Exception:
        return None


def _numval(v):
    """Unwrap a value that may be a dict (from _safe_param_value) or a bare number."""
    if isinstance(v, dict):
        return v.get("value")
    return v


# ──────────────────────────────────────────────────────────────────────
# Write helpers
# ──────────────────────────────────────────────────────────────────────

def _capture_param_snapshot(params_obj, param_names):
    """Snapshot current parameter values for before/after comparison."""
    snapshot = {}
    for name in param_names:
        val = _read_param(params_obj, name)
        if val is not None:
            snapshot[name] = val
    return snapshot


def _write_param(params_obj, name, expression):
    """Set a parameter value by expression string.

    Returns:
        (success: bool, error_message: str or None)
    """
    try:
        param = params_obj.itemByName(name)
        if param is None:
            return False, f"Parameter '{name}' not found"
        param.expression = str(expression)
        return True, None
    except Exception as e:
        return False, f"Failed to set '{name}': {e}"


def _build_diff(before_snapshot, after_snapshot, params_obj=None, label_map=None):
    """Build a structured diff from two parameter snapshots.

    Labels are resolved from *params_obj* (Fusion parameter collection,
    using _param_label) when available, falling back to *label_map* dict,
    then to the parameter name itself.
    """
    changes = []
    all_keys = set(before_snapshot.keys()) | set(after_snapshot.keys())
    for key in sorted(all_keys):
        before_val = before_snapshot.get(key)
        after_val = after_snapshot.get(key)
        if before_val != after_val:
            label = key
            if params_obj:
                p = None
                try:
                    p = params_obj.itemByName(key)
                except Exception:
                    pass
                if p:
                    label = _param_label(p)
            if label == key and label_map:
                label = label_map.get(key, key)
            changes.append({
                "parameter": key,
                "label": label,
                "before": before_val,
                "after": after_val,
            })
    return changes
