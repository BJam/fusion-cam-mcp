# ──────────────────────────────────────────────────────────────────────
# Base utilities and constants for Fusion 360 CAM query scripts.
#
# This is the first helper module loaded (sorted by filename).
# Provides imports, constants, defensive-access utilities, and all
# parameter category sets that other modules depend on.
# ──────────────────────────────────────────────────────────────────────

import adsk.core
import adsk.fusion
import adsk.cam
import math

# ──────────────────────────────────────────────────────────────────────
# Defensive access utilities
# ──────────────────────────────────────────────────────────────────────

def _is_proxy_str(val):
    """Check if a value is a Swig proxy string (not useful as serialized data)."""
    if isinstance(val, str):
        return "<adsk." in val or "proxy of" in val or "Swig Object" in val
    return False


def _safe_attr(obj, attr, default=None):
    """Safely read an attribute, returning *default* on any error or SWIG proxy."""
    try:
        val = getattr(obj, attr, default)
        if val is None or _is_proxy_str(val):
            return default
        return val
    except Exception:
        return default


def _safe_iter(collection):
    """Yield items from a Fusion collection, silently stopping on errors."""
    if collection is None:
        return
    try:
        count = collection.count
    except Exception:
        return
    for i in range(count):
        try:
            yield collection.item(i)
        except Exception:
            continue


# ──────────────────────────────────────────────────────────────────────
# CAM parameter category sets
# ──────────────────────────────────────────────────────────────────────

FEED_PARAMS = {
    "tool_feedCutting",
    "tool_feedEntry",
    "tool_feedExit",
    "tool_feedPlunge",
    "tool_feedRamp",
    "tool_feedRetract",
    "tool_feedTransition",
    "tool_feedPerTooth",
}

SPEED_PARAMS = {
    "tool_spindleSpeed",
    "tool_rampSpindleSpeed",
    "tool_clockwise",
}

ENGAGEMENT_PARAMS = {
    "stepover",
    "stepdown",
    "finishStepover",
    "finishStepdown",
    "optimalLoad",
    "loadDeviation",
    "maximumStepdown",
    "fineStepdown",
}

TOOL_GEOM_PARAMS = {
    "tool_diameter",
    "tool_numberOfFlutes",
    "tool_fluteLength",
    "tool_overallLength",
    "tool_shoulderLength",
    "tool_shaftDiameter",
    "tool_type",
    "tool_number",
    "tool_comment",
    "tool_description",
    "tool_bodyLength",
    "tool_cornerRadius",
    "tool_taperAngle",
    "tool_tipAngle",
}

STRATEGY_PARAMS = {
    "tolerance",
    "contourTolerance",
    "smoothingTolerance",
    "useStockToLeave",
    "stockToLeave",
    "axialStockToLeave",
    "finishStockToLeave",
    "finishAxialStockToLeave",
    "bothWays",
    "machineShallowAreas",
    "machineSteepAreas",
    "direction",
    "compensation",
    "compensationType",
}

LINKING_PARAMS = {
    "leadInRadius",
    "leadOutRadius",
    "leadInSweepAngle",
    "leadOutSweepAngle",
    "leadInVerticalRadius",
    "leadOutVerticalRadius",
    "rampType",
    "rampAngle",
    "rampDiameter",
    "rampClearanceHeight",
    "entryPositionType",
    "exitPositionType",
    "useRetracts",
    "keepToolDown",
    "liftHeight",
}

DRILLING_PARAMS = {
    "cycleType",
    "dwellTime",
    "dwellEnabled",
    "peckingDepth",
    "accumulatedPeckingDepth",
    "chipBreakDistance",
    "breakThroughDistance",
    "breakThroughFeedrate",
    "backBoreDistance",
    "threading",
    "pitch",
}

PASS_PARAMS = {
    "numberOfStepdowns",
    "useFinishingPasses",
    "finishingPasses",
    "doMultipleDepths",
    "restMachining",
    "restMachiningAdjustment",
    "useTabbing",
    "tabWidth",
    "tabHeight",
    "tabCount",
    "tabPositioning",
}

HEIGHT_PARAMS = {
    "clearanceHeight_value",
    "clearanceHeight_offset",
    "retractHeight_value",
    "retractHeight_offset",
    "feedHeight_value",
    "feedHeight_offset",
    "topHeight_value",
    "topHeight_offset",
    "bottomHeight_value",
    "bottomHeight_offset",
}

ALL_PARAM_CATEGORIES = {
    "feeds":      FEED_PARAMS,
    "speeds":     SPEED_PARAMS,
    "engagement": ENGAGEMENT_PARAMS,
    "tool":       TOOL_GEOM_PARAMS,
    "strategy":   STRATEGY_PARAMS,
    "heights":    HEIGHT_PARAMS,
    "linking":    LINKING_PARAMS,
    "drilling":   DRILLING_PARAMS,
    "passes":     PASS_PARAMS,
}

ALL_KNOWN_PARAMS = set()
for _cat_params in ALL_PARAM_CATEGORIES.values():
    ALL_KNOWN_PARAMS |= _cat_params

# Prefix rules for auto-categorizing parameters not in the explicit sets.
_AUTO_CATEGORY_RULES = [
    ("feeds",    lambda n: n.startswith("tool_feed")),
    ("speeds",   lambda n: n.startswith("tool_spindle") or n.startswith("tool_ramp")),
    ("tool",     lambda n: n.startswith("tool_")),
    ("heights",  lambda n: any(n.startswith(p) for p in (
        "clearanceHeight", "retractHeight", "feedHeight", "topHeight", "bottomHeight"))),
    ("linking",  lambda n: n.startswith(("leadIn", "leadOut", "ramp", "entry", "exit"))),
    ("drilling", lambda n: n.startswith(("cycle", "dwell", "pecking", "chipBreak",
                                         "breakThrough", "backBore", "threading", "pitch"))),
    ("passes",   lambda n: n.startswith(("numberOfStep", "finishing", "doMultiple",
                                         "restMachining", "useTab", "tab"))),
]


def _categorize_param(name):
    """Return the category name for an unknown parameter, or 'other'."""
    for category, test in _AUTO_CATEGORY_RULES:
        if test(name):
            return category
    return "other"


# ──────────────────────────────────────────────────────────────────────
# Other constants
# ──────────────────────────────────────────────────────────────────────

CAM_PRODUCT_TYPE = "CAMProductType"

OPERATION_TYPE_MAP = {
    0: "milling",
    1: "turning",
    2: "jet",
    3: "additive",
}

DISTANCE_UNIT_MAP = {0: "mm", 1: "cm", 2: "m", 3: "in", 4: "ft"}

DEFAULT_RAPID_FEED = 500.0       # cm/min (~200 ipm)
DEFAULT_TOOL_CHANGE_TIME = 15.0  # seconds

# Machine-related parameter names to read from setups.
_MACHINE_PARAM_NAMES = [
    "job_machine",
    "job_machine_manufacturer",
    "job_machine_type",
    "job_machine_configuration",
    "job_machine_configuration_id",
    "job_machine_build_strategy_id",
    "machine_dimension_x",
    "machine_dimension_y",
    "machine_dimension_z",
    "machineMaxTilt",
]

# Stock-related parameter names to read from setups.
_STOCK_PARAM_NAMES = [
    "job_stockMode",
    "job_stockFixedX",
    "job_stockFixedY",
    "job_stockFixedZ",
    "job_stockFixed_width",
    "job_stockFixed_height",
    "job_stockFixed_depth",
    "job_stockOffsetSide",
    "job_stockOffsetTop",
    "job_stockOffsetBottom",
    "job_stockExpandX",
    "job_stockExpandY",
    "job_stockExpandZ",
    "job_stockDiameter",
    "job_stockLength",
    "job_stockType",
]

# Operation parameters that are safe to write (feeds, speeds, engagement).
WRITABLE_OPERATION_PARAMS = FEED_PARAMS | SPEED_PARAMS | ENGAGEMENT_PARAMS

# Machine-level setup parameters that are safe to update.
MACHINE_WRITABLE_PARAMS = {
    "machine_dimension_x":         "Machine Dimension X",
    "machine_dimension_y":         "Machine Dimension Y",
    "machine_dimension_z":         "Machine Dimension Z",
    "machineMaxTilt":              "Max Tilt Angle",
}

# Spindle parameters that can be written via _write_machine_spindle.
SPINDLE_WRITABLE_PARAMS = {
    "maxSpindleSpeed":  "Max Spindle Speed (RPM)",
    "minSpindleSpeed":  "Min Spindle Speed (RPM)",
    "spindlePower":     "Spindle Power (kW)",
    "peakTorque":       "Peak Torque (Nm)",
    "peakTorqueSpeed":  "Peak Torque Speed (RPM)",
}
