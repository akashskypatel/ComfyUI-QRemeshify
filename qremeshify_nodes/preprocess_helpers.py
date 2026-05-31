"""Shared mesh preprocessing helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .artifacts import (
    build_mesh_artifact,
    build_sharp_artifact,
    parse_obj_payload,
    parse_sharp_payload,
)
from .blender_backend import bpy_available
from .backend_subprocess import preprocess_mesh_with_backend_subprocess
from .errors import QRemeshifyError
from .libigl_compat import require_igl
from .mesh_health import analyze_mesh_arrays, format_mesh_health_markdown
from .mesh_io import (
    prepare_mesh_workspace,
    prepare_output_workspace,
    write_triangle_obj,
)
from .sharp_features import generate_sharp_features, libigl_sharp_edges_available


def to_numpy(value):
    """Convert tensor/array-like to numpy array.
    
    Args:
        value: Input tensor/array-like
        
    Returns:
        Numpy array
    """
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    return np.asarray(value)


def extract_mesh_arrays(mesh_value):
    """Extract vertices and faces from MESH input.
    
    Args:
        mesh_value: MESH input value
        
    Returns:
        Tuple of (vertices, faces)
        
    Raises:
        QRemeshifyError: If MESH input is invalid
    """
    vertices = to_numpy(mesh_value.vertices)
    faces = to_numpy(mesh_value.faces)

    if vertices.ndim == 3:
        if vertices.shape[0] != 1:
            raise QRemeshifyError("MESH input must contain exactly one mesh item")
        vertices = vertices[0]
    if faces.ndim == 3:
        if faces.shape[0] != 1:
            raise QRemeshifyError("MESH input must contain exactly one mesh item")
        faces = faces[0]

    vertex_counts = getattr(mesh_value, "vertex_counts", None)
    face_counts = getattr(mesh_value, "face_counts", None)
    if vertex_counts is not None:
        vertex_counts = to_numpy(vertex_counts).reshape(-1)
        if vertex_counts.size != 1:
            raise QRemeshifyError("MESH input must contain exactly one mesh item")
        vertices = vertices[: int(vertex_counts[0])]
    if face_counts is not None:
        face_counts = to_numpy(face_counts).reshape(-1)
        if face_counts.size != 1:
            raise QRemeshifyError("MESH input must contain exactly one mesh item")
        faces = faces[: int(face_counts[0])]

    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise QRemeshifyError("MESH vertices must have shape (N, 3) or (1, N, 3)")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise QRemeshifyError("MESH faces must have shape (M, 3) or (1, M, 3)")
    if vertices.size == 0 or faces.size == 0:
        raise QRemeshifyError("MESH input has no usable faces")

    return np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int64)


def count_unique_edges(faces: np.ndarray | list[list[int]]) -> int:
    """Count unique undirected edges from polygon faces."""
    if len(faces) == 0:
        return 0
    edges: set[tuple[int, int]] = set()
    for face in faces:
        face_vertices = [int(vertex) for vertex in face]
        if len(face_vertices) < 2:
            continue
        for index, start in enumerate(face_vertices):
            end = face_vertices[(index + 1) % len(face_vertices)]
            edges.add(tuple(sorted((start, end))))
    return len(edges)


def build_mesh_stats(vertices, faces) -> dict[str, int]:
    """Build basic mesh stats for vertices, faces, edges, tris, and quads."""
    tri_count = 0
    quad_count = 0
    for face in faces:
        face_size = len(face)
        if face_size == 3:
            tri_count += 1
        elif face_size == 4:
            quad_count += 1
    return {
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "edge_count": int(count_unique_edges(faces)),
        "tri_count": int(tri_count),
        "quad_count": int(quad_count),
    }


def format_mesh_stats_markdown(
    input_stats: dict[str, int],
    output_stats: dict[str, int],
    input_health: dict[str, int | str] | None = None,
    output_health: dict[str, int | str] | None = None,
) -> str:
    """Format mesh stats as markdown."""
    sections = [
        "\n".join(
            [
                "## Mesh Stats",
                "",
                "| Mesh | Vertices | Faces | Edges | Tris | Quads |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
                f"| Input | {input_stats['vertex_count']} | {input_stats['face_count']} | {input_stats['edge_count']} | {input_stats['tri_count']} | {input_stats['quad_count']} |",
                f"| Output | {output_stats['vertex_count']} | {output_stats['face_count']} | {output_stats['edge_count']} | {output_stats['tri_count']} | {output_stats['quad_count']} |",
            ]
        )
    ]
    if input_health is not None and output_health is not None:
        sections.append(format_mesh_health_markdown(input_health, output_health))
    return "\n\n".join(sections)


def libigl_available() -> bool:
    """Check if libigl is available.
    
    Returns:
        True if libigl is available, False otherwise
    """
    try:
        import igl  # noqa: F401
    except ImportError:
        return False
    return True


def _require_igl():
    """Require libigl to be available."""
    return require_igl()


def load_triangle_mesh_with_libigl(mesh_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load triangle mesh using libigl.
    
    Args:
        mesh_path: Mesh file path
        
    Returns:
        Tuple of (vertices, faces)
        
    Raises:
        QRemeshifyError: If libigl fails to load the mesh
    """
    igl = _require_igl()
    vertices, faces = igl.read_triangle_mesh(str(mesh_path))
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if vertices.size == 0 or faces.size == 0:
        raise QRemeshifyError(f"libigl could not load a triangle mesh from: {mesh_path}")
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise QRemeshifyError("libigl returned vertices with an unexpected shape")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise QRemeshifyError(
            "backend='LIBIGL' requires a triangle mesh; non-triangular faces were returned"
        )
    return vertices, faces


def resolve_decimate_target_faces(
    face_count: int, decimate_target_faces: int, decimate_ratio: float
) -> int:
    """Resolve decimation target faces.
    
    Args:
        face_count: Current face count
        decimate_target_faces: Target number of faces
        decimate_ratio: Decimation ratio
        
    Returns:
        Resolved target face count
    """
    if face_count <= 0:
        return 0
    if decimate_target_faces > 0:
        return min(int(decimate_target_faces), face_count)
    if decimate_ratio < 0.999999:
        clamped_ratio = max(0.0, min(1.0, float(decimate_ratio)))
        return min(max(1, int(round(face_count * clamped_ratio))), face_count)
    return face_count


def decimate_mesh_with_trimesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    decimate_target_faces: int,
    decimate_ratio: float,
) -> tuple[np.ndarray, np.ndarray, bool, int]:
    """Decimate mesh using trimesh quadric decimation.

    Args:
        vertices: Vertex coordinates
        faces: Face indices
        decimate_target_faces: Target number of faces
        decimate_ratio: Decimation ratio

    Returns:
        Tuple of (reduced_vertices, reduced_faces, reached_target, target_faces)
    """
    target_faces = resolve_decimate_target_faces(
        len(faces),
        decimate_target_faces,
        decimate_ratio,
    )
    if target_faces >= len(faces):
        return vertices, faces, True, target_faces

    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError(
            "backend='TRIMESH' requires the 'trimesh' Python package to be installed"
        ) from exc

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
    )
    try:
        simplified = mesh.simplify_quadric_decimation(face_count=int(target_faces))
    except BaseException as exc:  # pragma: no cover
        raise QRemeshifyError(
            "TRIMESH decimation failed. Install trimesh's quadric decimation dependency "
            "with `pip install fast-simplification` in the active ComfyUI environment."
        ) from exc

    reduced_vertices = np.asarray(simplified.vertices, dtype=np.float64)
    reduced_faces = np.asarray(simplified.faces, dtype=np.int64)
    if reduced_vertices.size == 0 or reduced_faces.size == 0:
        raise QRemeshifyError("TRIMESH decimation returned an empty mesh")
    if reduced_vertices.ndim != 2 or reduced_vertices.shape[1] != 3:
        raise QRemeshifyError("TRIMESH decimation returned vertices with an unexpected shape")
    if reduced_faces.ndim != 2 or reduced_faces.shape[1] != 3:
        raise QRemeshifyError("TRIMESH decimation returned faces with an unexpected shape")
    return reduced_vertices, reduced_faces, len(reduced_faces) <= target_faces, target_faces


def decimate_mesh_with_libigl(
    vertices: np.ndarray,
    faces: np.ndarray,
    decimate_target_faces: int,
    decimate_ratio: float,
) -> tuple[np.ndarray, np.ndarray, bool, int]:
    """Decimate mesh using libigl.
    
    Args:
        vertices: Vertex coordinates
        faces: Face indices
        decimate_target_faces: Target number of faces
        decimate_ratio: Decimation ratio
        
    Returns:
        Tuple of (reduced_vertices, reduced_faces, reached_target, target_faces)
    """
    target_faces = resolve_decimate_target_faces(
        len(faces),
        decimate_target_faces,
        decimate_ratio,
    )
    if target_faces >= len(faces):
        return vertices, faces, True, target_faces

    igl = _require_igl()
    reached_target, reduced_vertices, reduced_faces, _, _ = igl.decimate(
        np.asarray(vertices, dtype=np.float64),
        np.asarray(faces, dtype=np.int32),
        int(target_faces),
    )
    reduced_vertices = np.asarray(reduced_vertices, dtype=np.float64)
    reduced_faces = np.asarray(reduced_faces, dtype=np.int64)
    if reduced_vertices.size == 0 or reduced_faces.size == 0:
        raise QRemeshifyError("libigl decimation returned an empty mesh")
    if reduced_vertices.ndim != 2 or reduced_vertices.shape[1] != 3:
        raise QRemeshifyError("libigl decimation returned vertices with an unexpected shape")
    if reduced_faces.ndim != 2 or reduced_faces.shape[1] != 3:
        raise QRemeshifyError("libigl decimation returned faces with an unexpected shape")
    return reduced_vertices, reduced_faces, bool(reached_target), target_faces


def inspect_libigl_manifold(faces: np.ndarray) -> tuple[bool, bool]:
    """Inspect mesh manifold properties using libigl.
    
    Args:
        faces: Face indices
        
    Returns:
        Tuple of (edge_manifold, vertex_manifold)
    """
    igl = _require_igl()
    edge_result = igl.is_edge_manifold(np.asarray(faces, dtype=np.int64))
    edge_manifold = bool(edge_result[0] if isinstance(edge_result, tuple) else edge_result)
    vertex_result = igl.is_vertex_manifold(np.asarray(faces, dtype=np.int64))
    vertex_manifold = bool(np.all(np.asarray(vertex_result, dtype=bool)))
    return edge_manifold, vertex_manifold


def coerce_mesh_input(input_mesh, output_dir: str, output_prefix: str):
    """Coerce mesh input to a standardized format.
    
    Args:
        input_mesh: Input mesh (file path, FILE_3D, or MESH)
        output_dir: Output directory
        output_prefix: Output prefix
        
    Returns:
        Tuple of (workspace_dir, source_mesh, stem, source_type)
        
    Raises:
        QRemeshifyError: If input_mesh is invalid
    """
    if isinstance(input_mesh, str):
        workspace_dir, source_mesh = prepare_mesh_workspace(
            input_mesh,
            output_dir,
            prefix="qremeshify_obj_",
        )
        stem = output_prefix.strip() or source_mesh.stem
        return workspace_dir, source_mesh, stem, "path"

    if hasattr(input_mesh, "save_to") and hasattr(input_mesh, "format"):
        workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_obj_")
        suffix = (
            f".{str(getattr(input_mesh, 'format', '')).lstrip('.')}"
            if getattr(input_mesh, "format", "")
            else ""
        )
        stem = output_prefix.strip() or "mesh"
        source_mesh = workspace_dir / f"{stem}_source{suffix}"
        saved_path = Path(input_mesh.save_to(str(source_mesh))).expanduser().resolve()
        if output_prefix.strip():
            stem = output_prefix.strip()
        elif saved_path.stem:
            stem = saved_path.stem
        return workspace_dir, saved_path, stem, "file3d"

    if hasattr(input_mesh, "vertices") and hasattr(input_mesh, "faces"):
        workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_obj_")
        stem = output_prefix.strip() or "mesh"
        return workspace_dir, None, stem, "mesh"

    raise QRemeshifyError(
        "input_mesh must be a file path string, FILE_3D, or MESH object"
    )


def resolve_preprocess_backend(
    backend: str,
    *,
    symmetry_requested: bool,
    decimate_requested: bool,
    fill_holes_requested: bool,
    allow_backend_fallback: bool,
) -> tuple[str, bool]:
    """Resolve the backend used for preprocessing."""
    resolved_backend = backend
    backend_fallback_used = False

    if backend == "AUTO":
        if symmetry_requested and bpy_available():
            resolved_backend = "BPY"
        elif fill_holes_requested:
            resolved_backend = "TRIMESH"
        elif decimate_requested and bpy_available():
            resolved_backend = "BPY"
        elif decimate_requested and libigl_available():
            resolved_backend = "LIBIGL"
        elif decimate_requested:
            resolved_backend = "TRIMESH"
        else:
            resolved_backend = "BPY" if bpy_available() else "TRIMESH"
    elif backend == "BPY" and not bpy_available():
        if allow_backend_fallback:
            if decimate_requested and not symmetry_requested and libigl_available():
                resolved_backend = "LIBIGL"
            else:
                resolved_backend = "TRIMESH"
            backend_fallback_used = True
        else:
            raise QRemeshifyError(
                "backend='BPY' requires Blender's Python modules to be installed and importable"
            )
    elif backend == "LIBIGL" and not libigl_available():
        if allow_backend_fallback:
            resolved_backend = "BPY" if bpy_available() else "TRIMESH"
            backend_fallback_used = True
        else:
            raise QRemeshifyError(
                "backend='LIBIGL' requires the 'libigl' Python package to be installed"
            )

    if symmetry_requested and resolved_backend != "BPY":
        if allow_backend_fallback and bpy_available():
            resolved_backend = "BPY"
            backend_fallback_used = True
        else:
            raise QRemeshifyError(
                "Symmetry preprocessing requires backend='BPY' unless backend fallback is enabled"
            )

    if decimate_requested and resolved_backend not in ("BPY", "LIBIGL", "TRIMESH"):
        if allow_backend_fallback:
            if bpy_available():
                resolved_backend = "BPY"
            elif libigl_available():
                resolved_backend = "LIBIGL"
            else:
                resolved_backend = "TRIMESH"
            backend_fallback_used = True
        else:
            raise QRemeshifyError(
                "Decimation requires backend='BPY', backend='LIBIGL', or backend='TRIMESH' unless backend fallback is enabled"
            )

    if fill_holes_requested and resolved_backend != "TRIMESH":
        if allow_backend_fallback:
            resolved_backend = "TRIMESH"
            backend_fallback_used = True
        else:
            raise QRemeshifyError(
                "Hole filling currently requires backend='TRIMESH' unless backend fallback is enabled"
            )

    return resolved_backend, backend_fallback_used


def initialize_preprocess_metadata(
    *,
    input_kind: str,
    backend: str,
    allow_backend_fallback: bool,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    decimate_requested: bool,
    decimate_target_faces: int,
    decimate_ratio: float,
    remove_degenerate_faces: bool,
    remove_duplicate_faces: bool,
    remove_unreferenced_vertices: bool,
    merge_duplicate_vertices: bool,
    fill_holes: bool,
    generate_sharp: bool,
) -> dict[str, str]:
    """Build the initial preprocessing metadata payload."""
    return {
        "input_kind": input_kind,
        "preprocessed": "true",
        "requested_backend": backend,
        "allow_backend_fallback": str(bool(allow_backend_fallback)).lower(),
        "symmetry_x": str(bool(symmetry_x)).lower(),
        "symmetry_y": str(bool(symmetry_y)).lower(),
        "symmetry_z": str(bool(symmetry_z)).lower(),
        "decimate_enabled": str(bool(decimate_requested)).lower(),
        "decimate_target_faces": str(int(decimate_target_faces)),
        "decimate_ratio": f"{float(decimate_ratio):.6f}",
        "remove_degenerate_faces": str(bool(remove_degenerate_faces)).lower(),
        "remove_duplicate_faces": str(bool(remove_duplicate_faces)).lower(),
        "remove_unreferenced_vertices": str(bool(remove_unreferenced_vertices)).lower(),
        "merge_duplicate_vertices": str(bool(merge_duplicate_vertices)).lower(),
        "fill_holes": str(bool(fill_holes)).lower(),
        "generate_sharp": str(bool(generate_sharp)).lower(),
    }


def update_preprocess_metadata(
    metadata: dict[str, str],
    *,
    input_stats: dict[str, int],
    output_stats: dict[str, int],
    resolved_backend: str,
    backend_fallback_used: bool,
    decimate_requested: bool,
    decimate_reached_target: bool,
    decimate_target_resolved: int,
    edge_manifold: bool | None,
    vertex_manifold: bool | None,
) -> None:
    """Populate final preprocessing metadata fields."""
    metadata["face_count"] = str(output_stats["face_count"])
    metadata["vertex_count"] = str(output_stats["vertex_count"])
    metadata["edge_count"] = str(output_stats["edge_count"])
    metadata["tri_count"] = str(output_stats["tri_count"])
    metadata["quad_count"] = str(output_stats["quad_count"])
    metadata["input_face_count"] = str(input_stats["face_count"])
    metadata["input_vertex_count"] = str(input_stats["vertex_count"])
    metadata["input_edge_count"] = str(input_stats["edge_count"])
    metadata["input_tri_count"] = str(input_stats["tri_count"])
    metadata["input_quad_count"] = str(input_stats["quad_count"])
    metadata["resolved_backend"] = resolved_backend
    metadata["backend_fallback_used"] = str(bool(backend_fallback_used)).lower()
    metadata["decimate_backend"] = resolved_backend if decimate_requested else "NONE"
    metadata["decimate_reached_target"] = str(bool(decimate_reached_target)).lower()
    metadata["decimate_target_resolved"] = str(int(decimate_target_resolved))
    if edge_manifold is not None:
        metadata["libigl_edge_manifold"] = str(bool(edge_manifold)).lower()
    if vertex_manifold is not None:
        metadata["libigl_vertex_manifold"] = str(bool(vertex_manifold)).lower()


def update_preprocess_health_metadata(
    metadata: dict[str, str],
    *,
    input_health: dict[str, int | str],
    output_health: dict[str, int | str],
) -> None:
    """Populate mesh health diagnostics into artifact metadata."""
    for key, value in input_health.items():
        metadata[f"input_{key}"] = str(value)
    for key, value in output_health.items():
        metadata[key] = str(value)


def resolve_sharp_backend(
    sharp_backend: str,
    *,
    allow_backend_fallback: bool,
) -> str:
    """Resolve the backend used for sharp-feature generation."""
    resolved_sharp_backend = sharp_backend
    if sharp_backend == "AUTO":
        if bpy_available():
            resolved_sharp_backend = "BPY"
        elif libigl_sharp_edges_available():
            resolved_sharp_backend = "LIBIGL"
        else:
            resolved_sharp_backend = "TRIMESH"
    elif sharp_backend == "BPY" and not bpy_available():
        if allow_backend_fallback:
            resolved_sharp_backend = (
                "LIBIGL" if libigl_sharp_edges_available() else "TRIMESH"
            )
        else:
            raise QRemeshifyError(
                "sharp_backend='BPY' requires Blender's Python modules to be installed and importable"
            )
    elif sharp_backend == "LIBIGL" and not libigl_sharp_edges_available():
        if allow_backend_fallback:
            resolved_sharp_backend = "BPY" if bpy_available() else "TRIMESH"
        else:
            raise QRemeshifyError(
                "sharp_backend='LIBIGL' requires a libigl build that exposes igl.sharp_edges"
            )
    return resolved_sharp_backend


def run_preprocess_backend_with_fallback(
    *,
    source_mesh: Path,
    output_obj_path: Path,
    resolved_backend: str,
    backend_fallback_used: bool,
    allow_backend_fallback: bool,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    decimate_enabled: bool,
    decimate_target_faces: int,
    decimate_ratio: float,
    remove_degenerate_faces: bool,
    remove_duplicate_faces: bool,
    remove_unreferenced_vertices: bool,
    merge_duplicate_vertices: bool,
    fill_holes: bool,
) -> tuple[dict, str, bool]:
    """Run the preprocess backend and optionally retry on BPY for libigl manifold failures."""
    attempted_fallback = False
    while True:
        try:
            result = preprocess_mesh_with_backend_subprocess(
                source_mesh,
                output_obj_path,
                resolved_backend,
                symmetry_x=symmetry_x,
                symmetry_y=symmetry_y,
                symmetry_z=symmetry_z,
                decimate_enabled=decimate_enabled,
                decimate_target_faces=decimate_target_faces,
                decimate_ratio=decimate_ratio,
                remove_degenerate_faces=remove_degenerate_faces,
                remove_duplicate_faces=remove_duplicate_faces,
                remove_unreferenced_vertices=remove_unreferenced_vertices,
                merge_duplicate_vertices=merge_duplicate_vertices,
                fill_holes=fill_holes,
            )
            return result, resolved_backend, backend_fallback_used
        except QRemeshifyError as exc:
            message = str(exc)
            if (
                resolved_backend == "LIBIGL"
                and allow_backend_fallback
                and not attempted_fallback
                and "requires a manifold triangle mesh" in message
                and bpy_available()
            ):
                resolved_backend = "BPY"
                backend_fallback_used = True
                attempted_fallback = True
                continue
            raise


def extract_preprocess_result_state(
    preprocess_result: dict,
    *,
    input_stats: dict[str, int] | None,
) -> tuple[
    dict[str, int] | None,
    dict[str, int | str] | None,
    dict[str, int | str] | None,
    bool,
    int,
    bool | None,
    bool | None,
]:
    """Extract stats and backend-state fields returned by the subprocess worker."""
    if input_stats is None:
        result_input_stats = preprocess_result.get("input_stats")
        if isinstance(result_input_stats, dict):
            input_stats = {
                "vertex_count": int(result_input_stats["vertex_count"]),
                "face_count": int(result_input_stats["face_count"]),
                "edge_count": int(result_input_stats["edge_count"]),
                "tri_count": int(result_input_stats.get("tri_count", result_input_stats["face_count"])),
                "quad_count": int(result_input_stats.get("quad_count", 0)),
            }

    input_health = preprocess_result.get("input_health")
    if not isinstance(input_health, dict):
        input_health = None
    output_health = preprocess_result.get("output_health")
    if not isinstance(output_health, dict):
        output_health = None
    decimate_reached_target = bool(
        preprocess_result.get("decimate_reached_target", True)
    )
    decimate_target_resolved = int(
        preprocess_result.get("decimate_target_resolved", 0)
    )
    edge_manifold = None
    vertex_manifold = None
    if "edge_manifold" in preprocess_result:
        edge_manifold = bool(preprocess_result["edge_manifold"])
    if "vertex_manifold" in preprocess_result:
        vertex_manifold = bool(preprocess_result["vertex_manifold"])
    return (
        input_stats,
        input_health,
        output_health,
        decimate_reached_target,
        decimate_target_resolved,
        edge_manifold,
        vertex_manifold,
    )


def build_sharp_outputs(
    *,
    generate_sharp: bool,
    sharp_backend: str,
    allow_backend_fallback: bool,
    workspace_dir: Path,
    stem: str,
    output_obj_path: Path,
    sharp_angle: float,
) -> tuple[str, object | None]:
    """Generate sharp features and build the returned sharp artifact."""
    sharp_path = ""
    sharp_artifact = None
    if not generate_sharp:
        return sharp_path, sharp_artifact

    resolved_sharp_backend = resolve_sharp_backend(
        sharp_backend,
        allow_backend_fallback=allow_backend_fallback,
    )
    sharp_output_path = workspace_dir / f"{stem}.sharp"
    sharp_path = str(
        generate_sharp_features(
            output_obj_path,
            output_obj_path,
            sharp_angle,
            sharp_output_path,
            resolved_sharp_backend,
        )
    )
    feature_rows = parse_sharp_payload(sharp_path)
    sharp_artifact = build_sharp_artifact(
        sharp_features_path=sharp_path,
        feature_rows=feature_rows,
        mesh_obj_path=str(output_obj_path),
        workspace_dir=str(workspace_dir),
        backend=resolved_sharp_backend,
        label=stem,
        metadata={
            "sharp_angle": f"{float(sharp_angle):.4f}",
            "source_backend": resolved_sharp_backend,
        },
    )
    return sharp_path, sharp_artifact


def materialize_preprocess_source(
    *,
    input_kind: str,
    input_mesh,
    workspace_dir: Path,
    stem: str,
    source_mesh: Path | None,
) -> tuple[Path, dict[str, int] | None]:
    """Materialize a concrete source mesh path for preprocessing."""
    input_stats: dict[str, int] | None = None
    if input_kind == "mesh":
        vertices, faces = extract_mesh_arrays(input_mesh)
        input_stats = build_mesh_stats(vertices, faces)
        source_mesh = workspace_dir / f"{stem}_source.obj"
        write_triangle_obj(source_mesh, vertices, faces)
    if source_mesh is None:
        raise QRemeshifyError("Preprocess source mesh path could not be resolved")
    return source_mesh, input_stats


def build_preprocess_outputs(
    *,
    output_obj_path: Path,
    workspace_dir: Path,
    source_mesh: Path,
    resolved_backend: str,
    stem: str,
    metadata: dict[str, str],
    vertices,
    faces,
    input_stats: dict[str, int],
    output_stats: dict[str, int],
    input_health: dict[str, int | str],
    output_health: dict[str, int | str],
    sharp_path: str,
    sharp_artifact,
) -> tuple[Path, Path, object, str, object | None, str]:
    """Build final preprocess outputs and markdown summary."""
    mesh_artifact = build_mesh_artifact(
        obj_path=str(output_obj_path),
        vertices=vertices,
        faces=faces,
        workspace_dir=str(workspace_dir),
        source_path=str(source_mesh),
        backend=resolved_backend,
        label=stem,
        metadata=metadata,
    )
    stats_markdown = format_mesh_stats_markdown(
        input_stats,
        output_stats,
        input_health=input_health,
        output_health=output_health,
    )
    return (
        output_obj_path,
        workspace_dir,
        mesh_artifact,
        sharp_path,
        sharp_artifact,
        stats_markdown,
    )


def preprocess_mesh_input(
    input_mesh,
    backend="AUTO",
    output_dir="",
    output_prefix="",
    symmetry_x=False,
    symmetry_y=False,
    symmetry_z=False,
    decimate_enabled=False,
    decimate_target_faces=0,
    decimate_ratio=1.0,
    remove_degenerate_faces=False,
    remove_duplicate_faces=False,
    remove_unreferenced_vertices=False,
    merge_duplicate_vertices=False,
    fill_holes=False,
    allow_backend_fallback=False,
    generate_sharp=False,
    sharp_angle=35.0,
    sharp_backend="AUTO",
):
    """Preprocess mesh input for QRemeshify.
    
    Args:
        input_mesh: Input mesh (file path, FILE_3D, or MESH)
        backend: Backend to use ("AUTO", "BPY", "LIBIGL")
        output_dir: Output directory
        output_prefix: Output prefix
        symmetry_x: Enable X-axis symmetry
        symmetry_y: Enable Y-axis symmetry
        symmetry_z: Enable Z-axis symmetry
        decimate_enabled: Enable decimation
        decimate_target_faces: Target number of faces
        decimate_ratio: Decimation ratio
        allow_backend_fallback: Allow backend fallback
        generate_sharp: Generate sharp features
        sharp_angle: Sharp angle threshold
        sharp_backend: Sharp features backend
        
    Returns:
        Tuple of (workspace_dir, output_obj_path, input_kind)
    """
    workspace_dir, source_mesh, stem, input_kind = coerce_mesh_input(
        input_mesh, output_dir, output_prefix
    )
    output_obj_path = workspace_dir / f"{stem}.obj"

    symmetry_requested = bool(symmetry_x or symmetry_y or symmetry_z)
    decimate_requested = bool(decimate_enabled)

    resolved_backend, backend_fallback_used = resolve_preprocess_backend(
        backend,
        symmetry_requested=symmetry_requested,
        decimate_requested=decimate_requested,
        fill_holes_requested=bool(fill_holes),
        allow_backend_fallback=allow_backend_fallback,
    )

    metadata = initialize_preprocess_metadata(
        input_kind=input_kind,
        backend=backend,
        allow_backend_fallback=allow_backend_fallback,
        symmetry_x=symmetry_x,
        symmetry_y=symmetry_y,
        symmetry_z=symmetry_z,
        decimate_requested=decimate_requested,
        decimate_target_faces=decimate_target_faces,
        decimate_ratio=decimate_ratio,
        remove_degenerate_faces=remove_degenerate_faces,
        remove_duplicate_faces=remove_duplicate_faces,
        remove_unreferenced_vertices=remove_unreferenced_vertices,
        merge_duplicate_vertices=merge_duplicate_vertices,
        fill_holes=fill_holes,
        generate_sharp=generate_sharp,
    )
    source_mesh, input_stats = materialize_preprocess_source(
        input_kind=input_kind,
        input_mesh=input_mesh,
        workspace_dir=workspace_dir,
        stem=stem,
        source_mesh=source_mesh,
    )

    preprocess_result, resolved_backend, backend_fallback_used = (
        run_preprocess_backend_with_fallback(
            source_mesh=source_mesh,
            output_obj_path=output_obj_path,
            resolved_backend=resolved_backend,
            backend_fallback_used=backend_fallback_used,
            allow_backend_fallback=allow_backend_fallback,
            symmetry_x=symmetry_x,
            symmetry_y=symmetry_y,
            symmetry_z=symmetry_z,
            decimate_enabled=decimate_enabled,
            decimate_target_faces=decimate_target_faces,
            decimate_ratio=decimate_ratio,
            remove_degenerate_faces=remove_degenerate_faces,
            remove_duplicate_faces=remove_duplicate_faces,
            remove_unreferenced_vertices=remove_unreferenced_vertices,
            merge_duplicate_vertices=merge_duplicate_vertices,
            fill_holes=fill_holes,
        )
    )

    vertices, faces = parse_obj_payload(str(output_obj_path))
    (
        input_stats,
        input_health,
        output_health,
        decimate_reached_target,
        decimate_target_resolved,
        edge_manifold,
        vertex_manifold,
    ) = extract_preprocess_result_state(
        preprocess_result,
        input_stats=input_stats,
    )

    output_stats = build_mesh_stats(vertices, faces)
    if input_stats is None:
        input_stats = output_stats
    if input_health is None:
        input_health = analyze_mesh_arrays(vertices, faces) if input_kind == "mesh" else {}
    if output_health is None:
        output_health = analyze_mesh_arrays(vertices, faces)
    update_preprocess_metadata(
        metadata,
        input_stats=input_stats,
        output_stats=output_stats,
        resolved_backend=resolved_backend,
        backend_fallback_used=backend_fallback_used,
        decimate_requested=decimate_requested,
        decimate_reached_target=decimate_reached_target,
        decimate_target_resolved=decimate_target_resolved,
        edge_manifold=edge_manifold,
        vertex_manifold=vertex_manifold,
    )
    if input_health and output_health:
        update_preprocess_health_metadata(
            metadata,
            input_health=input_health,
            output_health=output_health,
        )

    sharp_path, sharp_artifact = build_sharp_outputs(
        generate_sharp=generate_sharp,
        sharp_backend=sharp_backend,
        allow_backend_fallback=allow_backend_fallback,
        workspace_dir=workspace_dir,
        stem=stem,
        output_obj_path=output_obj_path,
        sharp_angle=sharp_angle,
    )
    return build_preprocess_outputs(
        output_obj_path=output_obj_path,
        workspace_dir=workspace_dir,
        source_mesh=source_mesh,
        resolved_backend=resolved_backend,
        stem=stem,
        metadata=metadata,
        vertices=vertices,
        faces=faces,
        input_stats=input_stats,
        output_stats=output_stats,
        input_health=input_health,
        output_health=output_health,
        sharp_path=sharp_path,
        sharp_artifact=sharp_artifact,
    )
