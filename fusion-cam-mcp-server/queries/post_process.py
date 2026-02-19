# ──────────────────────────────────────────────────────────────────────
# Query: post_process
# Post-processes operations or a setup to generate NC/G-code files.
#
# Params: setup_name (required), output_folder (required),
#         program_name (optional), program_number (optional),
#         operation_names (optional list), document_name (optional)
# Result: {outputFolder: str, operations: [...], programName: str}
# ──────────────────────────────────────────────────────────────────────

def run(params):
    import os

    dialog_err = _check_no_active_command()
    if dialog_err:
        return dialog_err

    document_name = params.get("document_name")
    cam, err = _get_cam(document_name)
    if err:
        return err

    setup_name = params.get("setup_name")
    output_folder = params.get("output_folder")

    if not setup_name:
        return {"success": False, "error": "Missing required parameter: setup_name"}
    if not output_folder:
        return {"success": False, "error": "Missing required parameter: output_folder"}

    setup, err = _find_setup_by_name(cam, setup_name)
    if err:
        return err

    operation_names = params.get("operation_names")
    program_name = params.get("program_name", setup_name)
    program_number = params.get("program_number", 1001)

    # Determine which operations to post-process
    if operation_names:
        operations = []
        for op_name in operation_names:
            op, op_err = _find_operation_by_name(cam, op_name, setup_name)
            if op_err:
                return op_err
            operations.append(op)

        op_collection = adsk.core.ObjectCollection.create()
        for op in operations:
            op_collection.add(op)
        post_ops = op_collection
    else:
        post_ops = setup

    # Check that toolpaths are generated for all operations
    ops_to_check = operations if operation_names else [
        setup.allOperations.item(i) for i in range(setup.allOperations.count)
        if not setup.allOperations.item(i).isSuppressed
    ]
    missing_toolpaths = [op.name for op in ops_to_check if not op.hasToolpath]

    if missing_toolpaths:
        return {
            "success": False,
            "error": f"The following operations do not have generated toolpaths: "
                     f"{missing_toolpaths}. Use generate_toolpaths first."
        }

    os.makedirs(output_folder, exist_ok=True)

    # Get the post configuration from the setup's machine
    post_url_str = None
    try:
        machine = setup.machine
        if machine:
            url_obj = machine.postURL
            if url_obj:
                try:
                    post_url_str = url_obj.toString()
                except Exception:
                    pass
    except Exception:
        pass

    # Resolve the post URL to a local .cps file path
    post_config = _resolve_post_config(cam, post_url_str)

    if not post_config:
        err_msg = "No post processor .cps file found on disk."
        if post_url_str:
            err_msg += f" Machine post URL: {post_url_str}."
        err_msg += (
            " The post processor may need to be downloaded "
            "in Fusion 360 first (open the Post Process dialog "
            "once to trigger download)."
        )
        return {"success": False, "error": err_msg}

    try:
        post_input = adsk.cam.PostProcessInput.create(
            program_name,
            post_config,
            output_folder,
            adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput
        )
        post_input.isOpenInEditor = False

        cam.postProcess(post_ops, post_input)

        generated_files = []
        try:
            for f in os.listdir(output_folder):
                fpath = os.path.join(output_folder, f)
                if os.path.isfile(fpath):
                    generated_files.append({
                        "filename": f,
                        "sizeBytes": os.path.getsize(fpath),
                    })
        except Exception:
            pass

        op_names = [op.name for op in ops_to_check]

        return {
            "outputFolder": output_folder,
            "programName": program_name,
            "postProcessor": post_config,
            "operations": op_names,
            "files": generated_files,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Post-processing failed: {e}",
        }


def _resolve_post_config(cam, post_url_str):
    """Resolve a post processor URL to a local .cps file path."""
    import os

    if not post_url_str:
        return None

    cps_name = post_url_str.split("://")[-1] if "://" in post_url_str else post_url_str

    search_folders = []
    try:
        pf = cam.personalPostFolder
        if pf:
            search_folders.append(pf)
    except Exception:
        pass
    try:
        pf = cam.postFolder
        if pf:
            search_folders.append(pf)
    except Exception:
        pass

    for folder in search_folders:
        candidate = os.path.join(folder, cps_name)
        if os.path.isfile(candidate):
            return candidate
        if os.path.isdir(folder):
            for root_dir, dirs, files in os.walk(folder):
                if cps_name in files:
                    return os.path.join(root_dir, cps_name)

    # Fallback: try any .cps in the post folders
    for folder in search_folders:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.endswith(".cps"):
                    return os.path.join(folder, f)

    return None
