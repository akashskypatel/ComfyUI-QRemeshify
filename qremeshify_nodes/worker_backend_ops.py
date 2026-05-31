"""Shared non-BPY worker backend operations for isolated subprocess execution."""

from __future__ import annotations

from pathlib import Path


def _count_unique_edges_from_faces(faces) -> int:
    """Count unique undirected edges for triangle faces."""
    import numpy as np

    face_array = np.asarray(faces, dtype=np.int64)
    if face_array.size == 0:
        return 0
    edges = set()
    for face in face_array:
        a, b, c = int(face[0]), int(face[1]), int(face[2])
        edges.add(tuple(sorted((a, b))))
        edges.add(tuple(sorted((b, c))))
        edges.add(tuple(sorted((c, a))))
    return len(edges)


def mesh_stats_from_arrays(vertices, faces) -> dict[str, int]:
    """Build vertex/face/edge/tri/quad stats from triangle mesh arrays."""
    return {
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "edge_count": int(_count_unique_edges_from_faces(faces)),
        "tri_count": int(len(faces)),
        "quad_count": 0,
    }


def resolve_target_faces(face_count: int, target_faces: int, ratio: float) -> int:
    """Resolve the requested decimation target face count."""
    if face_count <= 0:
        return 0
    if int(target_faces) > 0:
        return min(int(target_faces), int(face_count))
    if float(ratio) < 0.999999:
        clamped_ratio = max(0.0, min(1.0, float(ratio)))
        return min(max(1, int(round(face_count * clamped_ratio))), int(face_count))
    return int(face_count)


def collect_feature_lines(
    vertices,
    faces,
    sharp_edge_keys: set[tuple[int, int]],
    face_normals,
) -> list[str]:
    """Collect `.sharp` rows from sharp-edge keys and mesh topology."""
    import numpy as np
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
            edge_to_occurrences.setdefault(edge_key, []).append(
                (face_index, edge_index, oriented_edge)
            )

    feature_lines: list[str] = []
    for edge_key, occurrences in edge_to_occurrences.items():
        is_boundary = len(occurrences) == 1
        is_sharp = edge_key in sharp_edge_keys
        if not is_sharp and not is_boundary:
            continue
        face_index, edge_index, _ = occurrences[0]
        convexity = 0
        if len(occurrences) == 2:
            face_a, _, _ = occurrences[0]
            face_b, _, _ = occurrences[1]
            edge_start = vertices[edge_key[0]]
            other_vertex = next(
                vertex for vertex in faces[face_b].tolist() if vertex not in edge_key
            )
            signed_distance = np.dot(
                vertices[other_vertex] - edge_start,
                face_normals[face_a],
            )
            convexity = 1 if signed_distance <= 0.0 else 0
        feature_lines.append(f"{convexity},{face_index},{edge_index}")
    return feature_lines


def write_feature_lines(output_path: Path, feature_lines: list[str]) -> None:
    """Write `.sharp` payload lines to disk."""
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{len(feature_lines)}\n")
        for line in feature_lines:
            handle.write(f"{line}\n")


def _run_libigl_preprocess_backend(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run LIBIGL mesh preprocessing in the worker."""
    import numpy as np

    mesh_path = Path(payload["mesh_path"])
    output_obj_path = Path(payload["output_obj_path"])
    decimate_requested = bool(payload.get("decimate_enabled"))
    igl = _import_repo_module("libigl_compat").require_igl()
    vertices, faces = igl.read_triangle_mesh(str(mesh_path))
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if vertices.size == 0 or faces.size == 0:
        raise QRemeshifyError(f"libigl could not load a triangle mesh from: {mesh_path}")
    edge_result = igl.is_edge_manifold(np.asarray(faces, dtype=np.int64))
    edge_manifold = bool(edge_result[0] if isinstance(edge_result, tuple) else edge_result)
    vertex_result = igl.is_vertex_manifold(np.asarray(faces, dtype=np.int64))
    vertex_manifold = bool(np.all(np.asarray(vertex_result, dtype=bool)))
    input_stats = mesh_stats_from_arrays(vertices, faces)
    if decimate_requested:
        target_faces = resolve_target_faces(
            len(faces),
            int(payload.get("decimate_target_faces", 0)),
            float(payload.get("decimate_ratio", 1.0)),
        )
        if not (edge_manifold and vertex_manifold):
            raise QRemeshifyError(
                "backend='LIBIGL' decimation requires a manifold triangle mesh. "
                f"is_edge_manifold={edge_manifold}, is_vertex_manifold={vertex_manifold}"
            )
        reached_target, vertices, faces, _, _ = igl.decimate(
            np.asarray(vertices, dtype=np.float64),
            np.asarray(faces, dtype=np.int32),
            int(target_faces),
        )
        decimate_reached_target = bool(reached_target)
    else:
        target_faces = 0
        decimate_reached_target = True
    _import_repo_module("libigl_compat").write_triangle_obj_with_libigl(
        output_obj_path,
        vertices,
        faces,
    )
    output_stats = mesh_stats_from_arrays(vertices, faces)
    return {
        "output_obj_path": str(output_obj_path),
        "input_stats": input_stats,
        "output_stats": output_stats,
        "decimate_reached_target": bool(decimate_reached_target),
        "decimate_target_resolved": int(target_faces),
        "edge_manifold": bool(edge_manifold),
        "vertex_manifold": bool(vertex_manifold),
    }


def _run_trimesh_preprocess_backend(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run TRIMESH mesh preprocessing in the worker."""
    import numpy as np

    mesh_path = Path(payload["mesh_path"])
    output_obj_path = Path(payload["output_obj_path"])
    decimate_requested = bool(payload.get("decimate_enabled"))
    mesh_io = _import_repo_module("mesh_io")
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError(
            "backend='TRIMESH' requires the 'trimesh' Python package to be installed"
        ) from exc

    vertices, faces = mesh_io.load_triangle_mesh_with_trimesh(mesh_path)
    input_stats = mesh_stats_from_arrays(vertices, faces)
    if decimate_requested:
        target_faces = resolve_target_faces(
            len(faces),
            int(payload.get("decimate_target_faces", 0)),
            float(payload.get("decimate_ratio", 1.0)),
        )
        if target_faces < len(faces):
            mesh = trimesh.Trimesh(
                vertices=np.asarray(vertices, dtype=np.float64),
                faces=np.asarray(faces, dtype=np.int64),
                process=False,
            )
            try:
                simplified = mesh.simplify_quadric_decimation(
                    face_count=int(target_faces)
                )
            except BaseException as exc:  # pragma: no cover
                raise QRemeshifyError(
                    "TRIMESH decimation failed. Install trimesh's quadric decimation dependency "
                    "with `pip install fast-simplification` in the active ComfyUI environment."
                ) from exc
            vertices = np.asarray(simplified.vertices, dtype=np.float64)
            faces = np.asarray(simplified.faces, dtype=np.int64)
        decimate_reached_target = len(faces) <= target_faces
    else:
        target_faces = 0
        decimate_reached_target = True
    mesh_io.write_triangle_obj(output_obj_path, vertices, faces)
    output_stats = mesh_stats_from_arrays(vertices, faces)
    return {
        "output_obj_path": str(output_obj_path),
        "input_stats": input_stats,
        "output_stats": output_stats,
        "decimate_reached_target": bool(decimate_reached_target),
        "decimate_target_resolved": int(target_faces),
    }


PREPROCESS_BACKEND_HANDLERS = {
    "LIBIGL": _run_libigl_preprocess_backend,
    "TRIMESH": _run_trimesh_preprocess_backend,
}


def run_backend_preprocess(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run LIBIGL or TRIMESH mesh preprocessing in the worker."""
    backend = payload["backend"]
    handler = PREPROCESS_BACKEND_HANDLERS.get(backend)
    if handler is None:
        raise QRemeshifyError(f"Unsupported preprocessing backend: {backend}")
    return handler(
        payload,
        QRemeshifyError=QRemeshifyError,
        _import_repo_module=_import_repo_module,
    )


def _run_libigl_sharp_generation_backend(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run LIBIGL sharp-feature generation in the worker."""
    import numpy as np

    mesh_path = Path(payload["mesh_path"])
    normalized_obj_path = Path(payload["normalized_obj_path"])
    output_path = Path(payload["output_path"])
    sharp_angle = float(payload["sharp_angle"])
    mesh_io = _import_repo_module("mesh_io")
    igl = _import_repo_module("libigl_compat").require_igl()
    if not hasattr(igl, "sharp_edges"):
        raise QRemeshifyError(
            "sharp_backend='LIBIGL' requires an installed libigl build that exposes igl.sharp_edges"
        )
    vertices, faces = igl.read_triangle_mesh(str(mesh_path))
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    _import_repo_module("libigl_compat").write_triangle_obj_with_libigl(
        normalized_obj_path,
        vertices,
        faces,
    )
    sharp_result = igl.sharp_edges(vertices, faces, np.pi * (sharp_angle / 180.0))
    _, _, unique_edges, _, _, sharp_indices = sharp_result
    unique_edges = np.asarray(unique_edges, dtype=np.int64)
    sharp_indices = set(np.asarray(sharp_indices, dtype=np.int64).tolist())
    sharp_edge_keys = {
        tuple(sorted((int(unique_edge[0]), int(unique_edge[1]))))
        for unique_index, unique_edge in enumerate(unique_edges)
        if unique_index in sharp_indices
    }
    face_normals = mesh_io.compute_face_normals(vertices, faces)
    write_feature_lines(
        output_path,
        collect_feature_lines(vertices, faces, sharp_edge_keys, face_normals),
    )
    return {
        "normalized_obj_path": str(normalized_obj_path),
        "output_path": str(output_path),
    }


def _run_trimesh_sharp_generation_backend(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run TRIMESH sharp-feature generation in the worker."""
    import numpy as np

    mesh_path = Path(payload["mesh_path"])
    normalized_obj_path = Path(payload["normalized_obj_path"])
    output_path = Path(payload["output_path"])
    sharp_angle = float(payload["sharp_angle"])
    mesh_io = _import_repo_module("mesh_io")
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError(
            "backend='TRIMESH' requires the 'trimesh' Python package to be installed"
        ) from exc
    vertices, faces = mesh_io.load_triangle_mesh_with_trimesh(mesh_path)
    mesh_io.write_triangle_obj(normalized_obj_path, vertices, faces)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    adjacency_edges = np.asarray(mesh.face_adjacency_edges, dtype=np.int64)
    adjacency_angles = np.asarray(mesh.face_adjacency_angles, dtype=np.float64)
    sharp_threshold = np.pi * (sharp_angle / 180.0)
    sharp_edge_keys = {
        tuple(sorted((int(edge[0]), int(edge[1]))))
        for edge, angle in zip(adjacency_edges, adjacency_angles)
        if angle >= sharp_threshold
    }
    face_normals = mesh_io.compute_face_normals(vertices, faces)
    write_feature_lines(
        output_path,
        collect_feature_lines(vertices, faces, sharp_edge_keys, face_normals),
    )
    return {
        "normalized_obj_path": str(normalized_obj_path),
        "output_path": str(output_path),
    }


SHARP_BACKEND_HANDLERS = {
    "LIBIGL": _run_libigl_sharp_generation_backend,
    "TRIMESH": _run_trimesh_sharp_generation_backend,
}


def run_backend_sharp_generation(
    payload: dict,
    *,
    QRemeshifyError,
    _import_repo_module,
) -> dict:
    """Run LIBIGL or TRIMESH sharp-feature generation in the worker."""
    backend = payload["backend"]
    handler = SHARP_BACKEND_HANDLERS.get(backend)
    if handler is None:
        raise QRemeshifyError(f"Unsupported sharp feature backend: {backend}")
    return handler(
        payload,
        QRemeshifyError=QRemeshifyError,
        _import_repo_module=_import_repo_module,
    )


def run_qremeshify_backend(
    payload: dict,
    *,
    _import_repo_module,
) -> dict:
    """Run the native QRemeshify backend pipeline in the worker."""
    backend_module = _import_repo_module("backend")
    QuadwildBackend = backend_module.QuadwildBackend

    backend = QuadwildBackend(Path(payload["mesh_path"]))
    if payload["remesh"]:
        backend.remesh_and_field(
            True,
            payload.get("sharp_features_path", ""),
            float(payload["sharp_angle"]),
        )
        backend.trace()
    backend.quadrangulate(
        enable_smoothing=bool(payload["enable_smoothing"]),
        scale_fact=float(payload["scale_fact"]),
        fixed_chart_clusters=int(payload["fixed_chart_clusters"]),
        alpha=float(payload["alpha"]),
        ilp_method=payload["ilp_method"],
        time_limit=int(payload["time_limit"]),
        gap_limit=float(payload["gap_limit"]),
        minimum_gap=float(payload["minimum_gap"]),
        isometry=bool(payload["isometry"]),
        regularity_quadrilaterals=bool(payload["regularity_quadrilaterals"]),
        regularity_non_quadrilaterals=bool(payload["regularity_non_quadrilaterals"]),
        regularity_non_quadrilaterals_weight=float(
            payload["regularity_non_quadrilaterals_weight"]
        ),
        align_singularities=bool(payload["align_singularities"]),
        align_singularities_weight=float(payload["align_singularities_weight"]),
        repeat_losing_constraints_iterations=bool(
            payload["repeat_losing_constraints_iterations"]
        ),
        repeat_losing_constraints_quads=bool(payload["repeat_losing_constraints_quads"]),
        repeat_losing_constraints_non_quads=bool(
            payload["repeat_losing_constraints_non_quads"]
        ),
        repeat_losing_constraints_align=bool(
            payload["repeat_losing_constraints_align"]
        ),
        hard_parity_constraint=bool(payload["hard_parity_constraint"]),
        flow_config=payload["flow_config"],
        satsuma_config=payload["satsuma_config"],
        callback_time_limit=[float(v) for v in payload["callback_time_limit"]],
        callback_gap_limit=[float(v) for v in payload["callback_gap_limit"]],
    )
    final_path = backend.output_smoothed_path if payload["enable_smoothing"] else backend.output_path
    return {
        "remeshed_path": str(backend.remeshed_path),
        "traced_path": str(backend.traced_path),
        "output_path": str(backend.output_path),
        "output_smoothed_path": str(backend.output_smoothed_path),
        "final_path": str(final_path),
    }


BACKEND_OPERATION_HANDLERS = {
    "LIBIGL": {
        "preprocess_mesh_backend": _run_libigl_preprocess_backend,
        "generate_sharp_features_backend": _run_libigl_sharp_generation_backend,
    },
    "TRIMESH": {
        "preprocess_mesh_backend": _run_trimesh_preprocess_backend,
        "generate_sharp_features_backend": _run_trimesh_sharp_generation_backend,
    },
    "QREMESHIFY": {
        "run_qremeshify_backend": run_qremeshify_backend,
    },
}


def get_backend_operation_handlers(backend: str) -> dict[str, callable]:
    """Return the registered operation handlers for a backend."""
    return BACKEND_OPERATION_HANDLERS.get(str(backend).upper(), {})


def resolve_backend_operation_handler(
    backend: str,
    operation: str,
    *,
    QRemeshifyError,
):
    """Resolve one backend operation handler from the centralized registry."""
    handlers = get_backend_operation_handlers(backend)
    handler = handlers.get(operation)
    if handler is None:
        raise QRemeshifyError(
            f"Unsupported backend worker operation: backend={backend}, operation={operation}"
        )
    return handler
