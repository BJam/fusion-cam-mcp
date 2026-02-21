# ──────────────────────────────────────────────────────────────────────
# Query: get_document_info
# Returns info about a specific document (or the active document).
#
# Params: document_name (optional)
# Result: {name, units, hasCAM, setupCount, operationCount}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    document_name = params.get("document_name")
    doc, err = _get_document(document_name)
    if err:
        return err

    data = {
        "name": doc.name,
        "units": _get_document_units(doc),
    }

    try:
        cam_product = doc.products.itemByProductType(CAM_PRODUCT_TYPE)
        data["hasCAM"] = cam_product is not None
        if cam_product:
            cam = adsk.cam.CAM.cast(cam_product)
            data["setupCount"] = cam.setups.count if cam.setups else 0
            data["operationCount"] = cam.allOperations.count if cam.allOperations else 0
    except Exception:
        data["hasCAM"] = False

    return data
