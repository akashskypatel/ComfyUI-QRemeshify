"""Optional Blender-backed mesh preprocessing helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .errors import QRemeshifyError


def bpy_available() -> bool:
    """Check if Blender is available.
    
    Returns:
        bool: True if Blender is available, False otherwise
    """
    from .bpy_subprocess import bpy_available_via_subprocess

    return bpy_available_via_subprocess()


def _require_bpy():
    """Require Blender Python modules.
    
    Returns:
        tuple: Tuple of (bpy, bmesh, mathutils)
        
    Raises:
        QRemeshifyError: If Blender Python modules are not available
    """
    try:
        import bpy
        import bmesh
        import mathutils
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise QRemeshifyError(
            "backend='BPY' requires Blender's Python modules to be installed and importable"
        ) from exc
    return bpy, bmesh, mathutils


def _cleanup_imported_objects(bpy, imported_objects):
    """Clean up imported objects.
    
    Args:
        bpy: Blender Python module
        imported_objects: List of imported objects
    """
    for obj in imported_objects:
        mesh_data = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data is not None and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)


def _prepare_obj_for_bpy_import(mesh_path: Path):
    """Prepare OBJ file for Blender import.
    
    Args:
        mesh_path: Path to the mesh file
        
    Returns:
        tuple: Tuple of (mesh_path, temp_path)
    """
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
    """Import mesh with Blender.
    
    Args:
        mesh_path: Path to the mesh file
        
    Returns:
        tuple: Tuple of (imported_objects, temp_dir)
    """
    bpy, _, _ = _require_bpy()
    ext = mesh_path.suffix.lower()
    import_path, temp_dir = _prepare_obj_for_bpy_import(mesh_path)

    try:
        before = {obj.as_pointer() for obj in bpy.data.objects}
        if ext == ".obj":
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(
                    filepath=str(import_path),
                    forward_axis="Y",
                    up_axis="Z",
                )
            else:  # pragma: no cover - older Blender path
                bpy.ops.import_scene.obj(
                    filepath=str(import_path),
                    axis_forward="Y",
                    axis_up="Z",
                )
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


def _build_bmesh_from_objects(imported_objects, source_ext: str | None = None):
    """Build bmesh from imported objects.
    
    Args:
        imported_objects: List of imported objects
        
    Returns:
        bmesh: Merged bmesh
    """
    bpy, bmesh, _ = _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    merged = bmesh.new()

    for obj in imported_objects:
        evaluated_obj = obj.evaluated_get(depsgraph)
        mesh = evaluated_obj.to_mesh()
        try:
            temp_bm = bmesh.new()
            temp_bm.from_mesh(mesh)
            transform_matrix = evaluated_obj.matrix_world
            if source_ext in {".glb", ".gltf"}:
                transform_matrix = _matrix_without_gltf_basis_corrections(
                    obj,
                    transform_matrix,
                )
            bmesh.ops.transform(
                temp_bm, matrix=transform_matrix, verts=temp_bm.verts
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


def _is_gltf_basis_correction_matrix(matrix, tolerance: float = 1e-5) -> bool:
    """Return True if a transform looks like a pure glTF basis correction."""
    import math

    translation, rotation, scale = matrix.decompose()
    if translation.length > tolerance:
        return False
    if any(abs(component - 1.0) > tolerance for component in scale):
        return False

    euler = rotation.to_euler("XYZ")
    quarter_turn = math.pi / 2.0
    return (
        abs(abs(euler.x) - quarter_turn) <= 1e-4
        and abs(euler.y) <= 1e-4
        and abs(euler.z) <= 1e-4
    )


def _matrix_without_gltf_basis_corrections(obj, matrix_world):
    """Strip basis-only ancestor transforms introduced by Blender glTF import."""
    _, _, mathutils = _require_bpy()

    correction = mathutils.Matrix.Identity(4)
    current = obj.parent
    stack = []
    while current is not None:
        stack.append(current)
        current = current.parent

    for ancestor in reversed(stack):
        local_matrix = ancestor.matrix_local.copy()
        if _is_gltf_basis_correction_matrix(local_matrix):
            correction = correction @ local_matrix

    if correction == mathutils.Matrix.Identity(4):
        return matrix_world
    return correction.inverted() @ matrix_world


def _active_symmetry_axes(symmetry_x: bool, symmetry_y: bool, symmetry_z: bool):
    """Get active symmetry axes.
    
    Args:
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        
    Returns:
        list: List of active symmetry axes
    """
    return [
        (0, symmetry_x),
        (1, symmetry_y),
        (2, symmetry_z),
    ]


def _apply_symmetry_preprocess_to_bmesh(
    bm, symmetry_x: bool, symmetry_y: bool, symmetry_z: bool, tolerance: float
):
    """Apply symmetry preprocessing to bmesh.
    
    Args:
        bm: BMesh to process
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        tolerance: Tolerance for symmetry operations
    """
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
    """Mirror bmesh across axis.
    
    Args:
        bm: BMesh to process
        axis_index: Axis index to mirror across
    """
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
    """Apply symmetry postprocessing to bmesh.
    
    Args:
        bm: BMesh to process
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        tolerance: Tolerance for symmetry operations
    """
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
    """Write bmesh to OBJ file.
    
    Args:
        bm: BMesh to write
        obj_path: Path to write OBJ file
    """
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
    """Write sharp file from bmesh.
    
    Args:
        bm: BMesh to write
        sharp_angle: Sharp angle threshold
        output_path: Path to write sharp file
        
    Returns:
        Path: Path to written sharp file
    """
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
    """Normalize mesh to OBJ with Blender.
    
    Args:
        mesh_path: Path to input mesh
        output_obj_path: Path to output OBJ
        
    Returns:
        Path: Path to normalized OBJ
    """
    from .bpy_subprocess import normalize_mesh_to_obj_with_bpy_subprocess

    return normalize_mesh_to_obj_with_bpy_subprocess(mesh_path, output_obj_path)


def preprocess_mesh_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool = False,
    symmetry_y: bool = False,
    symmetry_z: bool = False,
    decimate_enabled: bool = False,
    decimate_target_faces: int = 0,
    decimate_ratio: float = 1.0,
    tolerance: float = 1e-5,
) -> Path:
    """Preprocess mesh with Blender.
    
    Args:
        mesh_path: Path to input mesh
        output_obj_path: Path to output OBJ
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        decimate_enabled: Whether to enable decimation
        decimate_target_faces: Target number of faces after decimation
        decimate_ratio: Decimation ratio
        tolerance: Tolerance for symmetry operations
        
    Returns:
        Path: Path to preprocessed OBJ
    """
    from .bpy_subprocess import preprocess_mesh_with_bpy_subprocess

    return preprocess_mesh_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x=symmetry_x,
        symmetry_y=symmetry_y,
        symmetry_z=symmetry_z,
        decimate_enabled=decimate_enabled,
        decimate_target_faces=decimate_target_faces,
        decimate_ratio=decimate_ratio,
        tolerance=tolerance,
    )


def preprocess_obj_with_symmetry_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    """Preprocess OBJ with symmetry using Blender.
    
    Args:
        mesh_path: Path to input mesh
        output_obj_path: Path to output OBJ
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        tolerance: Tolerance for symmetry operations
        
    Returns:
        Path: Path to preprocessed OBJ
    """
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
    """Postprocess OBJ with symmetry using Blender.
    
    Args:
        mesh_path: Path to input mesh
        output_obj_path: Path to output OBJ
        symmetry_x: Whether to apply symmetry on X axis
        symmetry_y: Whether to apply symmetry on Y axis
        symmetry_z: Whether to apply symmetry on Z axis
        tolerance: Tolerance for symmetry operations
        
    Returns:
        Path: Path to postprocessed OBJ
    """
    from .bpy_subprocess import postprocess_obj_with_symmetry_with_bpy_subprocess

    return postprocess_obj_with_symmetry_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x,
        symmetry_y,
        symmetry_z,
        tolerance,
    )
