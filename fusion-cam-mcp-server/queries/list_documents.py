# ──────────────────────────────────────────────────────────────────────
# Query: list_documents
# Returns all open Fusion 360 documents with CAM summary info.
#
# Params: (none)
# Result: {documents: [...], count: int, activeDocument: str}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    app = adsk.core.Application.get()
    if not app:
        return {"success": False, "error": "Fusion 360 application not available"}

    active_doc = app.activeDocument
    active_name = active_doc.name if active_doc else None

    documents = []
    for i in range(app.documents.count):
        doc = app.documents.item(i)
        doc_info = {
            "name": doc.name,
            "isActive": (doc.name == active_name),
        }

        try:
            cam_product = doc.products.itemByProductType(CAM_PRODUCT_TYPE)
            doc_info["hasCAM"] = cam_product is not None
            if cam_product:
                cam = adsk.cam.CAM.cast(cam_product)
                if cam:
                    doc_info["setupCount"] = cam.setups.count if cam.setups else 0
                    doc_info["operationCount"] = cam.allOperations.count if cam.allOperations else 0
        except Exception:
            doc_info["hasCAM"] = False

        doc_info["units"] = _get_document_units(doc)

        documents.append(doc_info)

    return {
        "documents": documents,
        "count": len(documents),
        "activeDocument": active_name,
    }
