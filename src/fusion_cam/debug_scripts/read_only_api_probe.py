# Read-only Fusion API snapshot for `fusion-cam debug`.
#
# Run (repo root, Fusion + bridge running):
#   fusion-cam debug --file src/fusion_cam/debug_scripts/read_only_api_probe.py
# Or after `pip install -e .`, from anywhere with the file path:
#   fusion-cam debug --file /path/to/read_only_api_probe.py
#
# Optional: pass document name — not used by this probe (always inspects active doc).

import adsk.core
import adsk.fusion
import adsk.cam

_CAM_TYPE = "CAMProductType"
_DESIGN_TYPE = "DesignProductType"
_DISTANCE_UNIT_MAP = {0: "mm", 1: "cm", 2: "m", 3: "in", 4: "ft"}


def _scalar(v):
    """Best-effort JSON-safe value from Fusion API objects."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        if "<adsk." in v or "Swig" in v or "proxy" in v.lower():
            return None
        return v
    try:
        s = str(v)
        if "<adsk." in s or "Swig" in s:
            return type(v).__name__
        return s
    except Exception:
        return type(v).__name__


def run(params):
    app = adsk.core.Application.get()
    if not app:
        return {"success": False, "error": "Application.get() returned None"}

    out = {
        "probe": "read_only_api_probe_v1",
        "application": {},
        "open_documents": [],
        "active_document": None,
    }

    # Omit user-identifying fields by default (safe to paste into agent logs).
    for attr in ("version", "isStartupComplete"):
        if hasattr(app, attr):
            try:
                val = getattr(app, attr)
                out["application"][attr] = _scalar(val)
            except Exception as e:
                out["application"][attr] = f"<read error: {e}>"

    try:
        for i in range(app.documents.count):
            doc = app.documents.item(i)
            out["open_documents"].append(
                {
                    "index": i,
                    "name": _scalar(getattr(doc, "name", None)),
                    "isActive": doc == app.activeDocument,
                }
            )
    except Exception as e:
        out["open_documents"] = [{"error": str(e)}]

    adoc = app.activeDocument
    if not adoc:
        return out

    ad = {"name": _scalar(adoc.name), "products": [], "design": None, "cam": None}

    try:
        design = adsk.fusion.Design.cast(
            adoc.products.itemByProductType(_DESIGN_TYPE)
        )
        if design and design.fusionUnitsManager:
            fum = design.fusionUnitsManager
            du = fum.distanceDisplayUnits
            ad["units"] = {
                "distanceDisplay": _DISTANCE_UNIT_MAP.get(int(du), str(du)),
            }
        else:
            ad["units"] = {"distanceDisplay": "unknown"}
    except Exception as e:
        ad["units_error"] = str(e)

    try:
        df = adoc.dataFile
        if df:
            ad["dataFile"] = {
                "name": _scalar(getattr(df, "name", None)),
                "id": _scalar(getattr(df, "id", None)),
            }
    except Exception:
        pass

    try:
        prods = adoc.products
        for i in range(prods.count):
            p = prods.item(i)
            pt = None
            try:
                pt = p.productType
            except Exception:
                pass
            ad["products"].append(
                {
                    "index": i,
                    "name": _scalar(getattr(p, "name", None)),
                    "productType": _scalar(pt),
                }
            )
    except Exception as e:
        ad["products_error"] = str(e)

    try:
        design = adoc.products.itemByProductType(_DESIGN_TYPE)
        if design:
            root = getattr(design, "rootComponent", None)
            ad["design"] = {
                "hasRootComponent": root is not None,
                "rootName": _scalar(getattr(root, "name", None)) if root else None,
            }
    except Exception as e:
        ad["design"] = {"error": str(e)}

    try:
        cam_raw = adoc.products.itemByProductType(_CAM_TYPE)
        if cam_raw:
            cam = adsk.cam.CAM.cast(cam_raw)
            n_setups = cam.setups.count if cam.setups else 0
            n_ops = cam.allOperations.count if cam.allOperations else 0
            ad["cam"] = {
                "setupCount": n_setups,
                "operationCount": n_ops,
            }
        else:
            ad["cam"] = None
    except Exception as e:
        ad["cam"] = {"error": str(e)}

    out["active_document"] = ad
    return out
