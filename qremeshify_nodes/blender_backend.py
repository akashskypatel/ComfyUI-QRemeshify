"""Optional Blender-backed mesh preprocessing helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .errors import QRemeshifyError


def bpy_available() -> bool:
    from .bpy_subprocess import bpy_available_via_subprocess

    return bpy_available_via_subprocess()


def _require_bpy():
    try:
        import bmesh
        import bpy
        import mathutils
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise QRemeshifyError(
            "backend='BPY' requires Blender's Python modules to be installed and importable"
        ) from exc
    return bpy, bmesh, mathutils


def _cleanup_imported_objects(bpy, imported_objects):
    for obj in imported_objects:
        mesh_data = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data is not None and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)


def _prepare_obj_for_bpy_import(mesh_path: Path):
    if mesh_path.suffix.lower() != ".obj":
        return mesh_path, None

    lines = mesh_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    needs_sanitization = any(
        line.lstrip().startswith("mtllib ") or line.lstrip().startswith("usemtl ")
        for line in lines
    )
    if not needs_sanitization:
        return mesh_path, None

    sanitized_lines = [
        line
        for line in lines
        if not line.lstrip().startswith("mtllib ")
        and not line.lstrip().startswith("usemtl ")
    ]
    temp_dir = Path(tempfile.mkdtemp(prefix="qremeshify_bpy_obj_"))
    sanitized_path = temp_dir / mesh_path.name
    sanitized_path.write_text("\n".join(sanitized_lines) + "\n", encoding="utf-8")
    return sanitized_path, temp_dir


def _import_mesh_with_bpy(mesh_path: Path):
    bpy, _, _ = _require_bpy()
    ext = mesh_path.suffix.lower()
    import_path, temp_dir = _prepare_obj_for_bpy_import(mesh_path)

    try:
        before = {obj.as_pointer() for obj in bpy.data.objects}
        if ext == ".obj":
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(filepath=str(import_path))
            else:  # pragma: no cover - older Blender path
                bpy.ops.import_scene.obj(filepath=str(import_path))
        elif ext == ".stl":
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=str(import_path))
            else:  # pragma: no cover
                bpy.ops.import_mesh.stl(filepath=str(import_path))
        elif ext == ".ply":
            if hasattr(bpy.ops.wm, "ply_import"):
                bpy.ops.wm.ply_import(filepath=str(import_path))
            else:  # pragma: no cover
                bpy.ops.import_mesh.ply(filepath=str(import_path))
        elif ext in {".glb", ".gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(import_path))
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(import_path))
        else:
            raise QRemeshifyError(
                f"backend='BPY' does not support importing: {mesh_path.suffix}"
            )

        imported_objects = [
            obj
            for obj in bpy.data.objects
            if obj.as_pointer() not in before and obj.type == "MESH"
        ]
        if not imported_objects:
            raise QRemeshifyError(
                f"Blender did not import any mesh objects from: {mesh_path}"
            )
        return bpy, imported_objects
    finally:
        if temp_dir is not None:
            for child in temp_dir.iterdir():
                child.unlink()
            temp_dir.rmdir()


def _build_bmesh_from_objects(imported_objects):
    bpy, bmesh, _ = _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    merged = bmesh.new()

    for obj in imported_objects:
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()
        try:
            temp_bm = bmesh.new()
            temp_bm.from_mesh(mesh)
            bmesh.ops.transform(
                temp_bm, matrix=evaluated_obj.matrix_world, verts=temp_bm.verts
            )
            temp_mesh = bpy.data.meshes.new(name="QRemeshifyTempMesh")
            try:
                temp_bm.to_mesh(temp_mesh)
                merged.from_mesh(temp_mesh)
            finally:
                bpy.data.meshes.remove(temp_mesh)
            temp_bm.free()
        finally:
            evaluated_obj.to_mesh_clear()

    bmesh.ops.triangulate(
        merged, faces=merged.faces, quad_method="SHORT_EDGE", ngon_method="BEAUTY"
    )
    merged.faces.ensure_lookup_table()
    merged.edges.ensure_lookup_table()
    merged.verts.ensure_lookup_table()
    return merged


def _active_symmetry_axes(symmetry_x: bool, symmetry_y: bool, symmetry_z: bool):
    return [
        (0, symmetry_x),
        (1, symmetry_y),
        (2, symmetry_z),
    ]


def _apply_symmetry_preprocess_to_bmesh(
    bm, symmetry_x: bool, symmetry_y: bool, symmetry_z: bool, tolerance: float
):
    _, bmesh, _ = _require_bpy()

    for axis_index, enabled in _active_symmetry_axes(
        symmetry_x, symmetry_y, symmetry_z
    ):
        if not enabled:
            continue

        plane_no = [0.0, 0.0, 0.0]
        plane_no[axis_index] = 1.0
        geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
        bmesh.ops.bisect_plane(
            bm,
            geom=geom,
            plane_co=(0.0, 0.0, 0.0),
            plane_no=plane_no,
            dist=tolerance,
            use_snap_center=True,
            clear_inner=True,
            clear_outer=False,
        )

        bm.verts.ensure_lookup_table()
        for vert in bm.verts:
            if abs(vert.co[axis_index]) <= tolerance:
                vert.co[axis_index] = 0.0

        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tolerance)
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()


def _mirror_bmesh_across_axis(bm, axis_index: int):
    _, bmesh, _ = _require_bpy()

    original_faces = list(bm.faces)
    result = bmesh.ops.duplicate(
        bm, geom=list(bm.verts) + list(bm.edges) + original_faces
    )
    dup_verts = [
        item for item in result["geom"] if isinstance(item, bmesh.types.BMVert)
    ]
    dup_faces = [
        item for item in result["geom"] if isinstance(item, bmesh.types.BMFace)
    ]
    for vert in dup_verts:
        vert.co[axis_index] *= -1.0

    if dup_faces:
        bmesh.ops.reverse_faces(bm, faces=dup_faces)


def _apply_symmetry_postprocess_to_bmesh(
    bm, symmetry_x: bool, symmetry_y: bool, symmetry_z: bool, tolerance: float
):
    _, bmesh, _ = _require_bpy()

    for axis_index, enabled in _active_symmetry_axes(
        symmetry_x, symmetry_y, symmetry_z
    ):
        if not enabled:
            continue
        _mirror_bmesh_across_axis(bm, axis_index)
        bm.verts.ensure_lookup_table()
        for vert in bm.verts:
            if abs(vert.co[axis_index]) <= tolerance:
                vert.co[axis_index] = 0.0
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tolerance)
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()


def _write_bmesh_obj(bm, obj_path: Path) -> None:
    bm.verts.index_update()
    bm.faces.index_update()
    with obj_path.open("w", encoding="utf-8") as handle:
        handle.write("# OBJ file\n")
        for vertex in bm.verts:
            handle.write(f"v {vertex.co.x:.6f} {vertex.co.y:.6f} {vertex.co.z:.6f}\n")
        for face in bm.faces:
            handle.write(
                f"vn {face.normal.x:.4f} {face.normal.y:.4f} {face.normal.z:.4f}\n"
            )
        for face_index, face in enumerate(bm.faces):
            indices = [f"{vert.index + 1}//{face_index + 1}" for vert in face.verts]
            handle.write(f"f {' '.join(indices)}\n")


def _write_sharp_file_from_bmesh(bm, sharp_angle: float, output_path: Path) -> Path:
    import math

    bm.faces.index_update()
    bm.edges.index_update()
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    face_set_data_layer = bm.faces.layers.int.get(".sculpt_face_set")
    feature_lines: list[str] = []
    for edge in bm.edges:
        if edge.is_wire:
            continue
        is_sharp = False
        if len(edge.link_faces) > 1:
            is_sharp = math.degrees(edge.calc_face_angle(0.0)) > sharp_angle
        is_material_boundary = (
            len(edge.link_faces) > 1
            and edge.link_faces[0].material_index != edge.link_faces[1].material_index
        )
        is_face_set_boundary = (
            face_set_data_layer is not None
            and len(edge.link_faces) > 1
            and edge.link_faces[0][face_set_data_layer]
            != edge.link_faces[1][face_set_data_layer]
        )
        if not (
            is_sharp
            or edge.is_boundary
            or edge.seam
            or not edge.smooth
            or is_material_boundary
            or is_face_set_boundary
        ):
            continue

        convexity = 1 if edge.is_convex else 0
        face = edge.link_faces[0]
        edge_index = next(
            index
            for index, face_edge in enumerate(face.edges)
            if face_edge.index == edge.index
        )
        feature_lines.append(f"{convexity},{face.index},{edge_index}")

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{len(feature_lines)}\n")
        for line in feature_lines:
            handle.write(f"{line}\n")
    return output_path


def normalize_mesh_to_obj_with_bpy(mesh_path: Path, output_obj_path: Path) -> Path:
    from .bpy_subprocess import normalize_mesh_to_obj_with_bpy_subprocess

    return normalize_mesh_to_obj_with_bpy_subprocess(mesh_path, output_obj_path)


def preprocess_obj_with_symmetry_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    from .bpy_subprocess import preprocess_obj_with_symmetry_with_bpy_subprocess

    return preprocess_obj_with_symmetry_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x,
        symmetry_y,
        symmetry_z,
        tolerance,
    )


def normalize_mesh_and_generate_sharp_with_bpy(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
) -> Path:
    from .bpy_subprocess import normalize_mesh_and_generate_sharp_with_bpy_subprocess

    return normalize_mesh_and_generate_sharp_with_bpy_subprocess(
        mesh_path,
        normalized_obj_path,
        sharp_angle,
        output_path,
    )


def postprocess_obj_with_symmetry_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    from .bpy_subprocess import postprocess_obj_with_symmetry_with_bpy_subprocess

    return postprocess_obj_with_symmetry_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x,
        symmetry_y,
        symmetry_z,
        tolerance,
    )
