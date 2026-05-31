"""Sharp-feature generation helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .bpy_subprocess import generate_sharp_features_with_backend_subprocess
from .errors import QRemeshifyError
from .libigl_compat import require_igl, write_triangle_obj_with_libigl
from .mesh_io import compute_face_normals, load_triangle_mesh_with_trimesh, write_triangle_obj


def _require_igl():
    """Require libigl to be installed."""
    return require_igl()


def libigl_sharp_edges_available() -> bool:
    """Check if libigl sharp_edges is available.
    
    Returns:
        True if sharp_edges is available, False otherwise
    """
    try:
        igl = _require_igl()
    except QRemeshifyError:
        return False
    return hasattr(igl, "sharp_edges")


def _require_igl_sharp_edges():
    """Require libigl sharp_edges to be available.
    
    Returns:
        libigl module
        
    Raises:
        QRemeshifyError: If sharp_edges is not available
    """
    igl = _require_igl()
    if not hasattr(igl, "sharp_edges"):
        raise QRemeshifyError(
            "sharp_backend='LIBIGL' requires an installed libigl build that exposes igl.sharp_edges"
        )
    return igl


def load_triangle_mesh_with_libigl(mesh_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a triangle mesh using libigl.
    
    Args:
        mesh_path: Path to the mesh file
        
    Returns:
        Tuple of (vertices, faces)
        
    Raises:
        QRemeshifyError: If libigl could not load the mesh
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


def collect_sharp_feature_lines(
    vertices: np.ndarray,
    faces: np.ndarray,
    sharp_edge_keys: set[tuple[int, int]],
    include_boundaries: bool,
) -> list[str]:
    """Collect sharp feature lines from a mesh.
    
    Args:
        vertices: Vertex coordinates
        faces: Face indices
        sharp_edge_keys: Set of sharp edge keys
        include_boundaries: Include boundary edges
        
    Returns:
        List of sharp feature lines
    """
    face_normals = compute_face_normals(vertices, faces)
    edge_to_occurrences: dict[tuple[int, int], list[tuple[int, int, tuple[int, int]]]] = {}
    for face_index, face in enumerate(faces):
        face_vertices = [int(face[0]), int(face[1]), int(face[2])]
        face_edges = [
            (face_vertices[0], face_vertices[1]),
            (face_vertices[1], face_vertices[2]),
            (face_vertices[2], face_vertices[0]),
        ]
        for edge_index, oriented_edge in enumerate(face_edges):
            edge_key = tuple(sorted(oriented_edge))
            edge_to_occurrences.setdefault(edge_key, []).append((face_index, edge_index, oriented_edge))

    output_lines: list[str] = []
    for edge_key, occurrences in edge_to_occurrences.items():
        is_boundary = len(occurrences) == 1
        is_sharp = edge_key in sharp_edge_keys
        if not is_sharp and not (include_boundaries and is_boundary):
            continue

        face_index, edge_index, _ = occurrences[0]
        convexity = 0
        if len(occurrences) == 2:
            face_a, _, _ = occurrences[0]
            face_b, _, _ = occurrences[1]
            edge_start = vertices[edge_key[0]]
            other_vertex = next(vertex for vertex in faces[face_b].tolist() if vertex not in edge_key)
            signed_distance = np.dot(vertices[other_vertex] - edge_start, face_normals[face_a])
            convexity = 1 if signed_distance <= 0.0 else 0

        output_lines.append(f"{convexity},{face_index},{edge_index}")

    return output_lines


def write_sharp_feature_file(output_path: Path, feature_lines: list[str]) -> Path:
    """Write sharp feature lines to a file.
    
    Args:
        output_path: Path to the output file
        feature_lines: List of feature lines
        
    Returns:
        Path to the output file
    """
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{len(feature_lines)}\n")
        for line in feature_lines:
            handle.write(f"{line}\n")
    return output_path


def generate_sharp_features_with_libigl(obj_path: Path, sharp_angle: float, output_path: Path) -> Path:
    """Generate sharp features using libigl.
    
    Args:
        obj_path: Path to the input OBJ file
        sharp_angle: Sharp angle threshold
        output_path: Path to the output sharp features file
        
    Returns:
        Path to the output sharp features file
    """
    igl = _require_igl_sharp_edges()
    vertices, faces = load_triangle_mesh_with_libigl(obj_path)
    write_triangle_obj_with_libigl(obj_path, vertices, faces)
    sharp_result = igl.sharp_edges(vertices, faces, np.pi * (sharp_angle / 180.0))
    _, _, unique_edges, _, _, sharp_indices = sharp_result
    unique_edges = np.asarray(unique_edges, dtype=np.int64)
    sharp_indices = set(np.asarray(sharp_indices, dtype=np.int64).tolist())
    sharp_edge_keys = {
        tuple(sorted((int(unique_edge[0]), int(unique_edge[1]))))
        for unique_index, unique_edge in enumerate(unique_edges)
        if unique_index in sharp_indices
    }
    output_lines = collect_sharp_feature_lines(vertices, faces, sharp_edge_keys, include_boundaries=True)
    return write_sharp_feature_file(output_path, output_lines)


def generate_sharp_features_with_trimesh(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
) -> Path:
    """Generate sharp features using trimesh.
    
    Args:
        mesh_path: Path to the input mesh file
        normalized_obj_path: Path to the normalized OBJ file
        sharp_angle: Sharp angle threshold
        output_path: Path to the output sharp features file
        
    Returns:
        Path to the output sharp features file
        
    Raises:
        QRemeshifyError: If trimesh is not installed
    """
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError("backend='TRIMESH' requires the 'trimesh' Python package to be installed") from exc

    vertices, faces = load_triangle_mesh_with_trimesh(mesh_path)
    write_triangle_obj(normalized_obj_path, vertices, faces)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    adjacency_edges = np.asarray(mesh.face_adjacency_edges, dtype=np.int64)
    adjacency_angles = np.asarray(mesh.face_adjacency_angles, dtype=np.float64)
    sharp_threshold = np.pi * (sharp_angle / 180.0)
    sharp_edge_keys = {
        tuple(sorted((int(edge[0]), int(edge[1]))))
        for edge, angle in zip(adjacency_edges, adjacency_angles)
        if angle >= sharp_threshold
    }
    output_lines = collect_sharp_feature_lines(vertices, faces, sharp_edge_keys, include_boundaries=True)
    return write_sharp_feature_file(output_path, output_lines)


def generate_sharp_features(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
    backend: str,
) -> Path:
    """Generate sharp features for a mesh.
    
    Args:
        mesh_path: Path to the input mesh file
        normalized_obj_path: Path to the normalized OBJ file
        sharp_angle: Sharp angle threshold
        output_path: Path to the output sharp features file
        backend: Backend to use ("BPY", "LIBIGL", or "TRIMESH")
        
    Returns:
        Path to the output sharp features file
        
    Raises:
        QRemeshifyError: If the backend is not supported or if required packages are not installed
    """
    if backend not in {"BPY", "LIBIGL", "TRIMESH"}:
        raise QRemeshifyError(f"Unsupported sharp feature backend: {backend}")
    return generate_sharp_features_with_backend_subprocess(
        mesh_path,
        normalized_obj_path,
        sharp_angle,
        output_path,
        backend,
    )
