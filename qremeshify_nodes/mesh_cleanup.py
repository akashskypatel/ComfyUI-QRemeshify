"""Conservative mesh cleanup helpers for preprocess backends."""

from __future__ import annotations

from collections import Counter

import numpy as np


def _normalize_faces(faces) -> list[list[int]]:
    return [[int(vertex) for vertex in face] for face in faces]


def _is_degenerate_face(vertices: np.ndarray, face: list[int], eps: float = 1e-12) -> bool:
    if len(face) < 3 or len(set(face)) < len(face):
        return True
    if any(index < 0 or index >= len(vertices) for index in face):
        return True
    face_vertices = vertices[np.asarray(face, dtype=np.int64)]
    origin = face_vertices[0]
    area_measure = 0.0
    for offset in range(1, len(face_vertices) - 1):
        edge_a = face_vertices[offset] - origin
        edge_b = face_vertices[offset + 1] - origin
        area_measure += np.linalg.norm(np.cross(edge_a, edge_b))
    return area_measure <= eps


def _merge_duplicate_vertices(
    vertices: np.ndarray,
    faces: list[list[int]],
    epsilon: float,
) -> tuple[np.ndarray, list[list[int]]]:
    if len(vertices) == 0:
        return vertices, faces
    if epsilon <= 0:
        epsilon = 1e-6
    quantized = np.round(vertices / float(epsilon)).astype(np.int64)
    key_to_new_index: dict[tuple[int, ...], int] = {}
    old_to_new: dict[int, int] = {}
    unique_vertices: list[np.ndarray] = []
    for old_index, key_row in enumerate(quantized):
        key = tuple(int(value) for value in key_row.tolist())
        if key in key_to_new_index:
            old_to_new[old_index] = key_to_new_index[key]
            continue
        new_index = len(unique_vertices)
        key_to_new_index[key] = new_index
        old_to_new[old_index] = new_index
        unique_vertices.append(vertices[old_index])
    remapped_faces = [[old_to_new[index] for index in face] for face in faces]
    return np.asarray(unique_vertices, dtype=np.float64), remapped_faces


def _remove_duplicate_faces(faces: list[list[int]]) -> list[list[int]]:
    seen: set[tuple[int, ...]] = set()
    unique_faces: list[list[int]] = []
    for face in faces:
        signature = tuple(sorted(face))
        if signature in seen:
            continue
        seen.add(signature)
        unique_faces.append(face)
    return unique_faces


def _remove_degenerate_faces(vertices: np.ndarray, faces: list[list[int]]) -> list[list[int]]:
    return [face for face in faces if not _is_degenerate_face(vertices, face)]


def _remove_unreferenced_vertices(
    vertices: np.ndarray,
    faces: list[list[int]],
) -> tuple[np.ndarray, list[list[int]]]:
    referenced = sorted({vertex for face in faces for vertex in face})
    if not referenced:
        width = vertices.shape[1] if vertices.ndim == 2 else 3
        return np.zeros((0, width), dtype=np.float64), []
    old_to_new = {old_index: new_index for new_index, old_index in enumerate(referenced)}
    new_vertices = vertices[np.asarray(referenced, dtype=np.int64)]
    remapped_faces = [[old_to_new[index] for index in face] for face in faces]
    return np.asarray(new_vertices, dtype=np.float64), remapped_faces


def cleanup_mesh_arrays(
    vertices,
    faces,
    *,
    remove_degenerate_faces: bool = False,
    remove_duplicate_faces: bool = False,
    remove_unreferenced_vertices: bool = False,
    merge_duplicate_vertices: bool = False,
    merge_duplicate_vertices_epsilon: float = 1e-6,
) -> tuple[np.ndarray, list[list[int]]]:
    """Apply conservative array-based cleanup passes in a stable order."""
    vertex_array = np.asarray(vertices, dtype=np.float64)
    face_rows = _normalize_faces(faces)
    if merge_duplicate_vertices:
        vertex_array, face_rows = _merge_duplicate_vertices(
            vertex_array,
            face_rows,
            merge_duplicate_vertices_epsilon,
        )
    if remove_degenerate_faces:
        face_rows = _remove_degenerate_faces(vertex_array, face_rows)
    if remove_duplicate_faces:
        face_rows = _remove_duplicate_faces(face_rows)
    if remove_unreferenced_vertices:
        vertex_array, face_rows = _remove_unreferenced_vertices(vertex_array, face_rows)
    return vertex_array, face_rows


def cleanup_bmesh_in_place(
    bm,
    *,
    remove_degenerate_faces: bool = False,
    remove_duplicate_faces: bool = False,
    remove_unreferenced_vertices: bool = False,
    merge_duplicate_vertices: bool = False,
    merge_duplicate_vertices_epsilon: float = 1e-6,
) -> None:
    """Apply conservative cleanup passes directly to a Blender bmesh."""
    import bmesh

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if merge_duplicate_vertices:
        bmesh.ops.remove_doubles(
            bm,
            verts=list(bm.verts),
            dist=float(merge_duplicate_vertices_epsilon),
        )
    if remove_degenerate_faces:
        bmesh.ops.dissolve_degenerate(
            bm,
            edges=list(bm.edges),
            dist=max(float(merge_duplicate_vertices_epsilon), 1e-12),
        )
        degenerate_faces = [
            face
            for face in bm.faces
            if len({vert.index for vert in face.verts}) < len(face.verts)
            or face.calc_area() <= 1e-12
        ]
        if degenerate_faces:
            bmesh.ops.delete(bm, geom=degenerate_faces, context="FACES")
    if remove_duplicate_faces:
        bm.faces.ensure_lookup_table()
        seen: Counter[tuple[int, ...]] = Counter()
        duplicate_faces = []
        for face in bm.faces:
            signature = tuple(sorted(int(vert.index) for vert in face.verts))
            seen[signature] += 1
            if seen[signature] > 1:
                duplicate_faces.append(face)
        if duplicate_faces:
            bmesh.ops.delete(bm, geom=duplicate_faces, context="FACES")
    if remove_unreferenced_vertices:
        loose_edges = [edge for edge in bm.edges if len(edge.link_faces) == 0]
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
        loose_verts = [
            vert for vert in bm.verts if len(vert.link_faces) == 0 and len(vert.link_edges) == 0
        ]
        if loose_verts:
            bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
