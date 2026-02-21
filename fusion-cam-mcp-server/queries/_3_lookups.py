# ──────────────────────────────────────────────────────────────────────
# Document, CAM, and object lookup functions.
#
# Depends on: _1_base.py (CAM_PRODUCT_TYPE), _2_params.py (_get_document_units)
# ──────────────────────────────────────────────────────────────────────

def _get_document(document_name=None):
    """Get a document by name, or the active document.
    Returns (document, error_dict) tuple.
    """
    app = adsk.core.Application.get()
    if not app:
        return None, {"success": False, "error": "Fusion 360 application not available"}

    if document_name:
        for doc in _safe_iter(app.documents):
            if doc.name == document_name:
                return doc, None
        available = [d.name for d in _safe_iter(app.documents)]
        return None, {
            "success": False,
            "error": f"Document '{document_name}' not found. Open documents: {available}. "
                     f"Use list_documents to see all open documents."
        }
    else:
        doc = app.activeDocument
        if not doc:
            return None, {"success": False, "error": "No document is open in Fusion 360"}
        return doc, None


def _get_cam(document_name=None):
    """Get a CAM product, optionally from a specific document.
    Returns (cam, error_dict) tuple.
    """
    doc, err = _get_document(document_name)
    if err:
        return None, err

    try:
        cam_product = doc.products.itemByProductType(CAM_PRODUCT_TYPE)
    except RuntimeError:
        cam_product = None
    if not cam_product:
        return None, {
            "success": False,
            "error": f"No CAM workspace found in document '{doc.name}'. "
                     f"Switch to the Manufacturing workspace first."
        }

    cam = adsk.cam.CAM.cast(cam_product)
    if not cam:
        return None, {"success": False, "error": "Failed to cast to CAM product"}

    return cam, None


def _find_setup_by_name(cam, name):
    """Find a setup by name. Returns (setup, error_dict) tuple."""
    for setup in cam.setups:
        if setup.name == name:
            return setup, None
    return None, {
        "success": False,
        "error": f"Setup '{name}' not found. Use get_setups to list available setups."
    }


def _find_operation_by_name(cam, operation_name, setup_name=None):
    """Find an operation by name, optionally within a specific setup."""
    if setup_name:
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return None, err
        for op in setup.allOperations:
            if op.name == operation_name:
                return op, None
        return None, {
            "success": False,
            "error": f"Operation '{operation_name}' not found in setup '{setup_name}'."
        }
    else:
        for op in cam.allOperations:
            if op.name == operation_name:
                return op, None
        return None, {
            "success": False,
            "error": f"Operation '{operation_name}' not found. Use get_operations to list available operations."
        }


def _find_library_by_name(library_name):
    """Find a material library by name.
    Returns (library, error_dict) tuple.
    """
    app = adsk.core.Application.get()
    if not app:
        return None, {"success": False, "error": "Fusion 360 application not available"}
    mat_libs = app.materialLibraries
    for lib in _safe_iter(mat_libs):
        if lib.name == library_name:
            return lib, None
    available = [lib.name for lib in _safe_iter(mat_libs)]
    return None, {
        "success": False,
        "error": f"Material library '{library_name}' not found. "
                 f"Available libraries: {available}"
    }


def _find_material_in_library(library_name, material_name):
    """Find a material in a named library.
    Returns (material, error_dict) tuple.
    """
    lib, err = _find_library_by_name(library_name)
    if err:
        return None, err
    for mat in _safe_iter(lib.materials):
        if mat.name == material_name:
            return mat, None
    return None, {
        "success": False,
        "error": f"Material '{material_name}' not found in library '{library_name}'. "
                 f"Use list_material_libraries to browse."
    }


def _find_body_by_name(document_name=None, body_name=None, setup_name=None):
    """Find a BRepBody by name, optionally scoped to a setup.

    Searches setup model bodies first (if setup_name given), then falls
    back to searching all bodies in the root component and sub-components.

    Returns (body, error_dict) tuple.
    """
    if not body_name:
        return None, {"success": False, "error": "Missing required parameter: body_name"}

    if setup_name:
        cam, err = _get_cam(document_name)
        if err:
            return None, err
        setup, err = _find_setup_by_name(cam, setup_name)
        if err:
            return None, err
        for body in _safe_iter(_safe_attr(setup, "models")):
            if _safe_attr(body, "name") == body_name:
                return body, None
        return None, {
            "success": False,
            "error": f"Body '{body_name}' not found in setup '{setup_name}'. "
                     f"Use get_setups to see model bodies."
        }

    doc, err = _get_document(document_name)
    if err:
        return None, err
    try:
        design = doc.products.itemByProductType("DesignProductType")
    except RuntimeError:
        design = None
    if not design:
        return None, {"success": False, "error": "No Design workspace found in document."}
    design = adsk.fusion.Design.cast(design)
    root = design.rootComponent

    def _search_component(comp):
        for body in _safe_iter(comp.bRepBodies):
            if body.name == body_name:
                return body
        return None

    found = _search_component(root)
    if found:
        return found, None

    for occ in _safe_iter(root.allOccurrences):
        found = _search_component(occ.component)
        if found:
            return found, None

    return None, {
        "success": False,
        "error": f"Body '{body_name}' not found in document. "
                 f"Use get_setups to see available model bodies."
    }
