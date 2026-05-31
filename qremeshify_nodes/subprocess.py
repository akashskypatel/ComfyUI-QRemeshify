"""Run bpy-backed work in a separate Python process."""

from __future__ import annotations

import json
import importlib
import types
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

if __package__:
    from .errors import QRemeshifyError
else:  # pragma: no cover - script execution path
    class QRemeshifyError(RuntimeError):
        """Fallback error type for direct script execution."""


def _worker_file() -> Path:
    """Get the path to the worker script."""
    return Path(__file__).resolve()


def _repo_root() -> Path:
    """Return the repository root that contains the qremeshify_nodes package."""
    return _worker_file().parent.parent


def _import_repo_module(module_name: str):
    """Import a qremeshify_nodes module from either package or script context."""
    repo_root = str(_repo_root())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    package_name = "qremeshify_nodes"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(_worker_file().parent)]
        package.__package__ = package_name
        sys.modules[package_name] = package
    return importlib.import_module(f"qremeshify_nodes.{module_name}")


def _run_subprocess(payload: dict) -> dict:
    """Run bpy operation in a separate Python process.
    
    Args:
        payload: Dictionary containing operation and parameters
        
    Returns:
        Dictionary with operation result
    """
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as handle:
        json.dump(payload, handle)
        payload_path = Path(handle.name)

    try:
        completed = subprocess.run(
            [sys.executable, str(_worker_file()), str(payload_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        payload_path.unlink(missing_ok=True)

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    response = None
    if stdout:
        for line in reversed(stdout.splitlines()):
            candidate = line.strip()
            if not candidate.startswith("{"):
                continue
            try:
                response = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue

    if completed.returncode != 0:
        error_message = None
        if isinstance(response, dict):
            error_message = response.get("error")
        if not error_message:
            error_message = stderr or stdout or "bpy subprocess exited without output"
        raise QRemeshifyError(
            f"bpy subprocess failed with exit code {completed.returncode}: {error_message}"
        )

    if not isinstance(response, dict):
        raise QRemeshifyError(
            f"bpy subprocess returned invalid JSON output: {stdout or '<empty>'}"
        )
    if response.get("status") != "ok":
        raise QRemeshifyError(response.get("error", "bpy subprocess returned an error"))
    return response


@lru_cache(maxsize=1)
def bpy_available_via_subprocess() -> bool:
    """Check if bpy is available via subprocess.
    
    Returns:
        bool: True if bpy is available, False otherwise
    """
    try:
        _run_subprocess({"operation": "probe", "probe_level": "BMESH"})
    except Exception:
        return False
    return True


def run_bpy_probe(probe_level: str) -> dict:
    """Run bpy probe operation.
    
    Args:
        probe_level: Level of probing to perform
        
    Returns:
        Dictionary with probe result
    """
    return _run_subprocess({"operation": "probe", "probe_level": probe_level})


def normalize_mesh_to_obj_with_subprocess(
    mesh_path: Path, output_obj_path: Path
) -> Path:
    """Normalize mesh to OBJ using bpy subprocess.
    
    Args:
        mesh_path: Path to input mesh
        output_obj_path: Path to output OBJ
        
    Returns:
        Path: Path to normalized OBJ
    """
    _run_subprocess(
        {
            "operation": "normalize_mesh_to_obj",
            "mesh_path": str(mesh_path),
            "output_obj_path": str(output_obj_path),
        }
    )
    return output_obj_path


def preprocess_obj_with_symmetry_with_subprocess(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    """Preprocess OBJ with symmetry using bpy subprocess.
    
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
    _run_subprocess(
        {
            "operation": "preprocess_obj_with_symmetry",
            "mesh_path": str(mesh_path),
            "output_obj_path": str(output_obj_path),
            "symmetry_x": symmetry_x,
            "symmetry_y": symmetry_y,
            "symmetry_z": symmetry_z,
            "tolerance": tolerance,
        }
    )
    return output_obj_path


def preprocess_mesh_with_subprocess(
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
    """Preprocess mesh using bpy subprocess.
    
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
    _run_subprocess(
        {
            "operation": "preprocess_mesh",
            "mesh_path": str(mesh_path),
            "output_obj_path": str(output_obj_path),
            "symmetry_x": symmetry_x,
            "symmetry_y": symmetry_y,
            "symmetry_z": symmetry_z,
            "decimate_enabled": decimate_enabled,
            "decimate_target_faces": decimate_target_faces,
            "decimate_ratio": decimate_ratio,
            "tolerance": tolerance,
        }
    )
    return output_obj_path


def normalize_mesh_and_generate_sharp_with_subprocess(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
) -> Path:
    """Normalize mesh and generate sharp edges using bpy subprocess.
    
    Args:
        mesh_path: Path to input mesh
        normalized_obj_path: Path to normalized OBJ
        sharp_angle: Sharp angle threshold
        output_path: Path to output OBJ
        
    Returns:
        Path: Path to output OBJ
    """
    _run_subprocess(
        {
            "operation": "normalize_mesh_and_generate_sharp",
            "mesh_path": str(mesh_path),
            "normalized_obj_path": str(normalized_obj_path),
            "sharp_angle": sharp_angle,
            "output_path": str(output_path),
        }
    )
    return output_path


def preprocess_mesh_with_backend_subprocess(
    mesh_path: Path,
    output_obj_path: Path,
    backend: str,
    symmetry_x: bool = False,
    symmetry_y: bool = False,
    symmetry_z: bool = False,
    decimate_enabled: bool = False,
    decimate_target_faces: int = 0,
    decimate_ratio: float = 1.0,
    tolerance: float = 1e-5,
) -> dict:
    """Preprocess a mesh with the selected backend in an isolated subprocess."""
    return _run_subprocess(
        {
            "operation": "preprocess_mesh_backend",
            "mesh_path": str(mesh_path),
            "output_obj_path": str(output_obj_path),
            "backend": backend,
            "symmetry_x": symmetry_x,
            "symmetry_y": symmetry_y,
            "symmetry_z": symmetry_z,
            "decimate_enabled": decimate_enabled,
            "decimate_target_faces": decimate_target_faces,
            "decimate_ratio": decimate_ratio,
            "tolerance": tolerance,
        }
    )


def generate_sharp_features_with_backend_subprocess(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
    backend: str,
) -> Path:
    """Generate sharp features with the selected backend in an isolated subprocess."""
    _run_subprocess(
        {
            "operation": "generate_sharp_features_backend",
            "mesh_path": str(mesh_path),
            "normalized_obj_path": str(normalized_obj_path),
            "sharp_angle": sharp_angle,
            "output_path": str(output_path),
            "backend": backend,
        }
    )
    return output_path


def run_qremeshify_backend_subprocess(
    mesh_path: Path,
    remesh: bool,
    sharp_features_path: str,
    sharp_angle: float,
    enable_smoothing: bool,
    scale_fact: float,
    fixed_chart_clusters: int,
    alpha: float,
    ilp_method: str,
    time_limit: int,
    gap_limit: float,
    minimum_gap: float,
    isometry: bool,
    regularity_quadrilaterals: bool,
    regularity_non_quadrilaterals: bool,
    regularity_non_quadrilaterals_weight: float,
    align_singularities: bool,
    align_singularities_weight: float,
    repeat_losing_constraints_iterations: bool,
    repeat_losing_constraints_quads: bool,
    repeat_losing_constraints_non_quads: bool,
    repeat_losing_constraints_align: bool,
    hard_parity_constraint: bool,
    flow_config: str,
    satsuma_config: str,
    callback_time_limit: list[float],
    callback_gap_limit: list[float],
) -> dict:
    """Run the native QRemeshify backend in an isolated subprocess."""
    return _run_subprocess(
        {
            "operation": "run_qremeshify_backend",
            "mesh_path": str(mesh_path),
            "remesh": bool(remesh),
            "sharp_features_path": sharp_features_path,
            "sharp_angle": float(sharp_angle),
            "enable_smoothing": bool(enable_smoothing),
            "scale_fact": float(scale_fact),
            "fixed_chart_clusters": int(fixed_chart_clusters),
            "alpha": float(alpha),
            "ilp_method": ilp_method,
            "time_limit": int(time_limit),
            "gap_limit": float(gap_limit),
            "minimum_gap": float(minimum_gap),
            "isometry": bool(isometry),
            "regularity_quadrilaterals": bool(regularity_quadrilaterals),
            "regularity_non_quadrilaterals": bool(regularity_non_quadrilaterals),
            "regularity_non_quadrilaterals_weight": float(
                regularity_non_quadrilaterals_weight
            ),
            "align_singularities": bool(align_singularities),
            "align_singularities_weight": float(align_singularities_weight),
            "repeat_losing_constraints_iterations": bool(
                repeat_losing_constraints_iterations
            ),
            "repeat_losing_constraints_quads": bool(repeat_losing_constraints_quads),
            "repeat_losing_constraints_non_quads": bool(
                repeat_losing_constraints_non_quads
            ),
            "repeat_losing_constraints_align": bool(
                repeat_losing_constraints_align
            ),
            "hard_parity_constraint": bool(hard_parity_constraint),
            "flow_config": flow_config,
            "satsuma_config": satsuma_config,
            "callback_time_limit": list(callback_time_limit),
            "callback_gap_limit": list(callback_gap_limit),
        }
    )


def postprocess_obj_with_symmetry_with_subprocess(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    """Postprocess OBJ with symmetry using bpy subprocess.
    
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
    _run_subprocess(
        {
            "operation": "postprocess_obj_with_symmetry",
            "mesh_path": str(mesh_path),
            "output_obj_path": str(output_obj_path),
            "symmetry_x": symmetry_x,
            "symmetry_y": symmetry_y,
            "symmetry_z": symmetry_z,
            "tolerance": tolerance,
        }
    )
    return output_obj_path


def _require_bpy():
    """Require bpy modules to be available.
    
    Returns:
        Tuple of (bpy, bmesh, mathutils)
        
    Raises:
        QRemeshifyError: If bpy modules are not available
    """
    try:
        import bpy
        import bmesh
        import mathutils
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise QRemeshifyError(
            "backend='BPY' requires Blender's Python modules to be installed and importable: "
            f"{exc}"
        ) from exc
    return bpy, bmesh, mathutils


def _cleanup_imported_objects(bpy, imported_objects):
    """Clean up imported objects.
    
    Args:
        bpy: bpy module
        imported_objects: List of imported objects
    """
    for obj in imported_objects:
        mesh_data = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data is not None and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)


def _prepare_obj_for_bpy_import(mesh_path: Path):
    """Prepare OBJ for bpy import by removing mtllib and usemtl lines.
    
    Args:
        mesh_path: Path to input mesh
        
    Returns:
        Tuple of (path to prepared mesh, temporary file path if created)
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
    """Import mesh using bpy.
    
    Args:
        mesh_path: Path to input mesh
        
    Returns:
        List of imported objects
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
        List of tuples (axis_index, enabled)
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
        bm: bmesh to process
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
    """Mirror bmesh across specified axis.
    
    Args:
        bm: bmesh to process
        axis_index: Axis index (0=X, 1=Y, 2=Z)
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
        bm: bmesh to process
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
        bm: bmesh to write
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
    """Write sharp edges from bmesh to sharp file.
    
    Args:
        bm: bmesh to process
        sharp_angle: Sharp angle threshold
        output_path: Path to write sharp file
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


def _decimation_ratio(current_faces: int, target_faces: int, ratio: float) -> float:
    """Calculate decimation ratio.
    
    Args:
        current_faces: Current number of faces
        target_faces: Target number of faces
        ratio: Decimation ratio
        
    Returns:
        Decimation ratio
    """
    resolved_ratio = max(0.0, min(1.0, float(ratio)))
    if target_faces > 0 and current_faces > 0:
        resolved_ratio = min(resolved_ratio, float(target_faces) / float(current_faces))
    return max(0.0, min(1.0, resolved_ratio))


def _decimate_bmesh(bm, target_faces: int, ratio: float):
    """Decimate bmesh.
    
    Args:
        bm: bmesh to decimate
        target_faces: Target number of faces
        ratio: Decimation ratio
        
    Returns:
        Decimated bmesh
    """
    bpy, bmesh, _ = _require_bpy()
    current_faces = len(bm.faces)
    resolved_ratio = _decimation_ratio(current_faces, target_faces, ratio)
    if resolved_ratio >= 0.999999:
        return bm

    temp_mesh = bpy.data.meshes.new(name="QRemeshifyDecimateMesh")
    temp_obj = bpy.data.objects.new("QRemeshifyDecimateObject", temp_mesh)
    bpy.context.scene.collection.objects.link(temp_obj)
    decimated_bm = None
    try:
        bm.to_mesh(temp_mesh)
        modifier = temp_obj.modifiers.new(name="QRemeshifyDecimate", type="DECIMATE")
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = resolved_ratio
        if hasattr(modifier, "use_collapse_triangulate"):
            modifier.use_collapse_triangulate = True

        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_obj = temp_obj.evaluated_get(depsgraph)
        evaluated_mesh = evaluated_obj.to_mesh()
        try:
            decimated_bm = bmesh.new()
            decimated_bm.from_mesh(evaluated_mesh)
        finally:
            evaluated_obj.to_mesh_clear()
    finally:
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        bpy.data.meshes.remove(temp_mesh)

    bmesh.ops.triangulate(
        decimated_bm,
        faces=decimated_bm.faces,
        quad_method="SHORT_EDGE",
        ngon_method="BEAUTY",
    )
    decimated_bm.faces.ensure_lookup_table()
    decimated_bm.edges.ensure_lookup_table()
    decimated_bm.verts.ensure_lookup_table()
    bm.free()
    return decimated_bm


def _run_probe(probe_level: str) -> dict:
    """Run probe to check bpy availability.
    
    Args:
        probe_level: Probe level (IMPORT_ONLY, APP_INFO, FULL)
        
    Returns:
        Probe result
    """
    details = ["Imported bpy successfully"]
    import bpy

    if probe_level == "IMPORT_ONLY":
        return {"probe_level": probe_level, "details": " | ".join(details)}

    import mathutils

    details.append(f"Blender version: {bpy.app.version_string}")
    details.append(f"Background mode: {bpy.app.background}")
    details.append(f"Scene count: {len(bpy.data.scenes)}")
    details.append(f"Object count: {len(bpy.data.objects)}")
    vector = mathutils.Vector((1.0, 2.0, 3.0))
    details.append(f"Vector length: {vector.length:.4f}")
    if probe_level == "APP_INFO":
        return {"probe_level": probe_level, "details": " | ".join(details)}

    mesh = bpy.data.meshes.new(name="qremeshify_bpy_smoke_mesh")
    details.append("Created temporary bpy.data mesh")
    try:
        mesh.from_pydata(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            [],
            [(0, 1, 2)],
        )
        mesh.update()
        details.append(
            f"Mesh vertices: {len(mesh.vertices)}, polygons: {len(mesh.polygons)}"
        )
        if probe_level == "MESH_DATA":
            return {"probe_level": probe_level, "details": " | ".join(details)}

        import bmesh

        bm = bmesh.new()
        try:
            bmesh.ops.create_cube(bm, size=1.0)
            details.append(f"BMesh verts: {len(bm.verts)}, faces: {len(bm.faces)}")
        finally:
            bm.free()
    finally:
        bpy.data.meshes.remove(mesh)
        details.append("Removed temporary bpy.data mesh")

    return {"probe_level": probe_level, "details": " | ".join(details)}


def _mesh_stats_from_bmesh(bm) -> dict[str, int]:
    """Build vertex/face/edge stats from a bmesh."""
    return {
        "vertex_count": int(len(bm.verts)),
        "face_count": int(len(bm.faces)),
        "edge_count": int(len(bm.edges)),
    }


def _handle_probe(payload: dict) -> dict:
    """Handle probe worker operation."""
    return _run_probe(payload.get("probe_level", "APP_INFO"))


def _handle_preprocess_mesh_backend(payload: dict) -> dict:
    """Handle backend-agnostic preprocess operation."""
    if payload["backend"] != "BPY":
        return _import_repo_module("worker_backend_ops").run_backend_preprocess(
            payload,
            QRemeshifyError=QRemeshifyError,
            _import_repo_module=_import_repo_module,
        )

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
            target_faces = _import_repo_module("worker_backend_ops").resolve_target_faces(
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
    """Handle backend-agnostic sharp feature generation operation."""
    if payload["backend"] != "BPY":
        return _import_repo_module("worker_backend_ops").run_backend_sharp_generation(
            payload,
            QRemeshifyError=QRemeshifyError,
            _import_repo_module=_import_repo_module,
        )

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


def _handle_run_qremeshify_backend(payload: dict) -> dict:
    """Handle native QRemeshify backend operation."""
    return _import_repo_module("worker_backend_ops").run_qremeshify_backend(
        payload,
        _import_repo_module=_import_repo_module,
    )


def _handle_normalize_mesh_to_obj(payload: dict) -> dict:
    """Handle OBJ normalization via BPY."""
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
    """Handle symmetry-only preprocessing via BPY."""
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
    """Handle full BPY mesh preprocessing."""
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
    """Handle BPY normalization plus sharp-feature extraction."""
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
    """Handle postprocess symmetry mirroring via BPY."""
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


WORKER_OPERATION_HANDLERS = {
    "probe": _handle_probe,
    "preprocess_mesh_backend": _handle_preprocess_mesh_backend,
    "generate_sharp_features_backend": _handle_generate_sharp_features_backend,
    "run_qremeshify_backend": _handle_run_qremeshify_backend,
    "normalize_mesh_to_obj": _handle_normalize_mesh_to_obj,
    "preprocess_obj_with_symmetry": _handle_preprocess_obj_with_symmetry,
    "preprocess_mesh": _handle_preprocess_mesh,
    "normalize_mesh_and_generate_sharp": _handle_normalize_mesh_and_generate_sharp,
    "postprocess_obj_with_symmetry": _handle_postprocess_obj_with_symmetry,
}


def _dispatch_worker(payload: dict) -> dict:
    """Dispatch worker to perform operations."""
    operation = payload["operation"]
    handler = WORKER_OPERATION_HANDLERS.get(operation)
    if handler is None:
        raise QRemeshifyError(f"Unsupported bpy subprocess operation: {operation}")
    return handler(payload)


def _worker_main(argv: list[str]) -> int:
    """Main worker function to handle operations.
    
    Args:
        argv: Command line arguments
        
    Returns:
        Exit code
    """
    payload_path = Path(argv[1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    try:
        response = _dispatch_worker(payload)
    except Exception as exc:  # pragma: no cover - environment dependent
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        )
        return 1

    print(json.dumps({"status": "ok", **response}))
    return 0


if __name__ == "__main__":  # pragma: no cover - subprocess entrypoint
    raise SystemExit(_worker_main(sys.argv))
