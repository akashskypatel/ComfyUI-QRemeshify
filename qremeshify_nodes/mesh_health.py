"""Mesh health analysis helpers for preprocessing diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np


def _normalize_faces(faces) -> list[list[int]]:
    return [[int(vertex) for vertex in face] for face in faces]


def _degenerate_face_count(vertices: np.ndarray, faces: list[list[int]], eps: float = 1e-12) -> int:
    degenerate = 0
    for face in faces:
        if len(face) < 3 or len(set(face)) < len(face):
            degenerate += 1
            continue
        if any(index < 0 or index >= len(vertices) for index in face):
            degenerate += 1
            continue
        face_vertices = vertices[np.asarray(face, dtype=np.int64)]
        origin = face_vertices[0]
        area_measure = 0.0
        for offset in range(1, len(face_vertices) - 1):
            edge_a = face_vertices[offset] - origin
            edge_b = face_vertices[offset + 1] - origin
            area_measure += np.linalg.norm(np.cross(edge_a, edge_b))
        if area_measure <= eps:
            degenerate += 1
    return int(degenerate)


def _edge_topology_counts(faces: list[list[int]]) -> tuple[int, int]:
    edge_counts: Counter[tuple[int, int]] = Counter()
    for face in faces:
        if len(face) < 2:
            continue
        for index, start in enumerate(face):
            end = face[(index + 1) % len(face)]
            edge_counts[tuple(sorted((int(start), int(end))))] += 1
    boundary = sum(1 for count in edge_counts.values() if count == 1)
    non_manifold = sum(1 for count in edge_counts.values() if count > 2)
    return int(boundary), int(non_manifold)


def _connected_component_count(faces: list[list[int]]) -> int:
    adjacency: dict[int, set[int]] = defaultdict(set)
    referenced_vertices: set[int] = set()
    for face in faces:
        for vertex in face:
            referenced_vertices.add(int(vertex))
        for index, start in enumerate(face):
            end = face[(index + 1) % len(face)]
            start = int(start)
            end = int(end)
            adjacency[start].add(end)
            adjacency[end].add(start)
    if not referenced_vertices:
        return 0
    visited: set[int] = set()
    components = 0
    for start in referenced_vertices:
        if start in visited:
            continue
        components += 1
        stack = [start]
        visited.add(start)
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, ()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                stack.append(neighbor)
    return int(components)


def analyze_mesh_arrays(vertices, faces) -> dict[str, int | str]:
    """Analyze mesh topology health from generic vertices/faces arrays."""
    vertex_array = np.asarray(vertices, dtype=np.float64)
    face_rows = _normalize_faces(faces)
    face_signatures = [tuple(sorted(face)) for face in face_rows if len(face) >= 3]
    duplicate_face_count = sum(count - 1 for count in Counter(face_signatures).values() if count > 1)
    referenced_vertices = {
        int(vertex)
        for face in face_rows
        for vertex in face
        if 0 <= int(vertex) < len(vertex_array)
    }
    unreferenced_vertex_count = max(0, int(len(vertex_array) - len(referenced_vertices)))
    degenerate_face_count = _degenerate_face_count(vertex_array, face_rows)
    boundary_edge_count, non_manifold_edge_count = _edge_topology_counts(face_rows)
    component_count = _connected_component_count(face_rows)
    score = (
        degenerate_face_count
        + duplicate_face_count
        + boundary_edge_count
        + non_manifold_edge_count
        + (1 if component_count > 1 else 0)
    )
    if score == 0:
        status = "HEALTHY"
    elif degenerate_face_count > 0 or non_manifold_edge_count > 0:
        status = "RISKY"
    else:
        status = "WARN"
    return {
        "status": status,
        "degenerate_face_count": int(degenerate_face_count),
        "duplicate_face_count": int(duplicate_face_count),
        "boundary_edge_count": int(boundary_edge_count),
        "non_manifold_edge_count": int(non_manifold_edge_count),
        "unreferenced_vertex_count": int(unreferenced_vertex_count),
        "component_count": int(component_count),
        "is_watertight": "true" if boundary_edge_count == 0 and non_manifold_edge_count == 0 else "false",
    }


def analyze_bmesh_health(bm) -> dict[str, int | str]:
    """Analyze mesh topology health directly from a Blender bmesh."""
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    vertices = np.asarray([[vert.co.x, vert.co.y, vert.co.z] for vert in bm.verts], dtype=np.float64)
    faces = [[int(vert.index) for vert in face.verts] for face in bm.faces]
    health = analyze_mesh_arrays(vertices, faces)
    health["loose_edge_count"] = int(sum(1 for edge in bm.edges if len(edge.link_faces) == 0))
    health["loose_vertex_count"] = int(sum(1 for vert in bm.verts if len(vert.link_edges) == 0))
    if (health["loose_edge_count"] or health["loose_vertex_count"]) and health["status"] == "HEALTHY":
        health["status"] = "WARN"
    return health


def format_mesh_health_markdown(input_health: dict[str, int | str], output_health: dict[str, int | str]) -> str:
    """Format mesh health diagnostics as markdown."""
    metrics = [
        ("Status", "status"),
        ("Degenerate Faces", "degenerate_face_count"),
        ("Duplicate Faces", "duplicate_face_count"),
        ("Boundary Edges", "boundary_edge_count"),
        ("Non-Manifold Edges", "non_manifold_edge_count"),
        ("Unreferenced Vertices", "unreferenced_vertex_count"),
        ("Connected Components", "component_count"),
        ("Watertight", "is_watertight"),
    ]
    if "loose_edge_count" in input_health or "loose_edge_count" in output_health:
        metrics.append(("Loose Edges", "loose_edge_count"))
    if "loose_vertex_count" in input_health or "loose_vertex_count" in output_health:
        metrics.append(("Loose Vertices", "loose_vertex_count"))
    lines = [
        "## Mesh Health",
        "",
        "| Metric | Input | Output |",
        "| --- | ---: | ---: |",
    ]
    for label, key in metrics:
        lines.append(f"| {label} | {input_health.get(key, 0)} | {output_health.get(key, 0)} |")
    return "\n".join(lines)
