"""BPY-specific worker operations for isolated subprocess execution."""

from __future__ import annotations

from pathlib import Path


def build_bpy_operation_handlers(
    *,
    _run_probe,
    _import_mesh_with_bpy,
    _build_bmesh_from_objects,
    _cleanup_imported_objects,
    _apply_symmetry_preprocess_to_bmesh,
    _apply_symmetry_postprocess_to_bmesh,
    _decimate_bmesh,
    _write_bmesh_obj,
    _write_sharp_file_from_bmesh,
    _mesh_stats_from_bmesh,
    resolve_target_faces,
) -> dict[str, callable]:
    """Build the BPY worker operation registry."""

    def _handle_probe(payload: dict) -> dict:
        return _run_probe(payload.get("probe_level", "APP_INFO"))

    def _handle_preprocess_mesh_backend(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        output_obj_path = Path(payload["output_obj_path"])
        decimate_requested = bool(payload.get("decimate_enabled"))
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            input_stats = _mesh_stats_from_bmesh(bm)
            if payload["symmetry_x"] or payload["symmetry_y"] or payload["symmetry_z"]:
                _apply_symmetry_preprocess_to_bmesh(
                    bm,
                    payload["symmetry_x"],
                    payload["symmetry_y"],
                    payload["symmetry_z"],
                    payload.get("tolerance", 1e-5),
                )
            if decimate_requested:
                target_faces = resolve_target_faces(
                    len(bm.faces),
                    int(payload.get("decimate_target_faces", 0)),
                    float(payload.get("decimate_ratio", 1.0)),
                )
                bm = _decimate_bmesh(
                    bm,
                    int(payload.get("decimate_target_faces", 0)),
                    float(payload.get("decimate_ratio", 1.0)),
                )
                decimate_reached_target = len(bm.faces) <= target_faces
            else:
                target_faces = 0
                decimate_reached_target = True
            output_stats = _mesh_stats_from_bmesh(bm)
            _write_bmesh_obj(bm, output_obj_path)
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {
            "output_obj_path": str(output_obj_path),
            "input_stats": input_stats,
            "output_stats": output_stats,
            "decimate_reached_target": bool(decimate_reached_target),
            "decimate_target_resolved": int(target_faces),
        }

    def _handle_generate_sharp_features_backend(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        normalized_obj_path = Path(payload["normalized_obj_path"])
        output_path = Path(payload["output_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            _write_bmesh_obj(bm, normalized_obj_path)
            _write_sharp_file_from_bmesh(
                bm,
                float(payload["sharp_angle"]),
                output_path,
            )
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {
            "normalized_obj_path": str(normalized_obj_path),
            "output_path": str(output_path),
        }

    def _handle_normalize_mesh_to_obj(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        output_obj_path = Path(payload["output_obj_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            _write_bmesh_obj(bm, output_obj_path)
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {"output_obj_path": str(output_obj_path)}

    def _handle_preprocess_obj_with_symmetry(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        output_obj_path = Path(payload["output_obj_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            _apply_symmetry_preprocess_to_bmesh(
                bm,
                payload["symmetry_x"],
                payload["symmetry_y"],
                payload["symmetry_z"],
                payload.get("tolerance", 1e-5),
            )
            _write_bmesh_obj(bm, output_obj_path)
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {"output_obj_path": str(output_obj_path)}

    def _handle_preprocess_mesh(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        output_obj_path = Path(payload["output_obj_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            if payload["symmetry_x"] or payload["symmetry_y"] or payload["symmetry_z"]:
                _apply_symmetry_preprocess_to_bmesh(
                    bm,
                    payload["symmetry_x"],
                    payload["symmetry_y"],
                    payload["symmetry_z"],
                    payload.get("tolerance", 1e-5),
                )
            if payload.get("decimate_enabled"):
                bm = _decimate_bmesh(
                    bm,
                    int(payload.get("decimate_target_faces", 0)),
                    float(payload.get("decimate_ratio", 1.0)),
                )
            _write_bmesh_obj(bm, output_obj_path)
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {"output_obj_path": str(output_obj_path)}

    def _handle_normalize_mesh_and_generate_sharp(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        normalized_obj_path = Path(payload["normalized_obj_path"])
        output_path = Path(payload["output_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            _write_bmesh_obj(bm, normalized_obj_path)
            _write_sharp_file_from_bmesh(
                bm,
                payload["sharp_angle"],
                output_path,
            )
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {
            "normalized_obj_path": str(normalized_obj_path),
            "output_path": str(output_path),
        }

    def _handle_postprocess_obj_with_symmetry(payload: dict) -> dict:
        mesh_path = Path(payload["mesh_path"])
        output_obj_path = Path(payload["output_obj_path"])
        bpy, imported_objects = _import_mesh_with_bpy(mesh_path)
        bm = None
        try:
            bm = _build_bmesh_from_objects(imported_objects, mesh_path.suffix.lower())
            _apply_symmetry_postprocess_to_bmesh(
                bm,
                payload["symmetry_x"],
                payload["symmetry_y"],
                payload["symmetry_z"],
                payload.get("tolerance", 1e-5),
            )
            _write_bmesh_obj(bm, output_obj_path)
        finally:
            if bm is not None:
                bm.free()
            _cleanup_imported_objects(bpy, imported_objects)
        return {"output_obj_path": str(output_obj_path)}

    return {
        "probe": _handle_probe,
        "preprocess_mesh_backend": _handle_preprocess_mesh_backend,
        "generate_sharp_features_backend": _handle_generate_sharp_features_backend,
        "normalize_mesh_to_obj": _handle_normalize_mesh_to_obj,
        "preprocess_obj_with_symmetry": _handle_preprocess_obj_with_symmetry,
        "preprocess_mesh": _handle_preprocess_mesh,
        "normalize_mesh_and_generate_sharp": _handle_normalize_mesh_and_generate_sharp,
        "postprocess_obj_with_symmetry": _handle_postprocess_obj_with_symmetry,
    }
