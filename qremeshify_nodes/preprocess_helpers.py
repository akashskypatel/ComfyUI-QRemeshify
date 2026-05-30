"""Shared mesh preprocessing helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .artifacts import build_mesh_artifact, mesh_arrays_to_lists, parse_obj_payload
from .blender_backend import bpy_available, preprocess_mesh_with_bpy
from .errors import QRemeshifyError
from .mesh_io import (
    load_triangle_mesh_with_trimesh,
    prepare_mesh_workspace,
    prepare_output_workspace,
    write_triangle_obj,
)


def to_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    return np.asarray(value)


def extract_mesh_arrays(mesh_value):
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


def coerce_mesh_input(input_mesh, output_dir: str, output_prefix: str):
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
):
    workspace_dir, source_mesh, stem, input_kind = coerce_mesh_input(
        input_mesh, output_dir, output_prefix
    )
    output_obj_path = workspace_dir / f"{stem}.obj"

    requires_bpy = (
        bool(symmetry_x or symmetry_y or symmetry_z)
        or bool(decimate_enabled)
        or decimate_target_faces > 0
        or decimate_ratio < 0.999999
    )

    resolved_backend = backend
    if backend == "AUTO":
        if requires_bpy and bpy_available():
            resolved_backend = "BPY"
        else:
            resolved_backend = "BPY" if bpy_available() else "TRIMESH"

    if requires_bpy and resolved_backend != "BPY":
        raise QRemeshifyError(
            "Symmetry and Blender-based decimation require backend='BPY'"
        )

    metadata = {
        "input_kind": input_kind,
        "preprocessed": "true",
        "symmetry_x": str(bool(symmetry_x)).lower(),
        "symmetry_y": str(bool(symmetry_y)).lower(),
        "symmetry_z": str(bool(symmetry_z)).lower(),
        "decimate_enabled": str(bool(decimate_enabled)).lower(),
        "decimate_target_faces": str(int(decimate_target_faces)),
        "decimate_ratio": f"{float(decimate_ratio):.6f}",
    }

    if input_kind == "mesh":
        vertices, faces = extract_mesh_arrays(input_mesh)
        if requires_bpy:
            source_mesh = workspace_dir / f"{stem}_source.obj"
            write_triangle_obj(source_mesh, vertices, faces)
            preprocess_mesh_with_bpy(
                source_mesh,
                output_obj_path,
                symmetry_x=symmetry_x,
                symmetry_y=symmetry_y,
                symmetry_z=symmetry_z,
                decimate_enabled=decimate_enabled,
                decimate_target_faces=decimate_target_faces,
                decimate_ratio=decimate_ratio,
            )
            vertices, faces = parse_obj_payload(str(output_obj_path))
        else:
            write_triangle_obj(output_obj_path, vertices, faces)
            vertices, faces = mesh_arrays_to_lists(vertices, faces)
    elif (
        source_mesh.suffix.lower() == ".obj"
        and not requires_bpy
        and source_mesh != output_obj_path
    ):
        output_obj_path.write_bytes(source_mesh.read_bytes())
        vertices, faces = parse_obj_payload(str(output_obj_path))
    elif source_mesh.suffix.lower() == ".obj" and not requires_bpy:
        vertices, faces = parse_obj_payload(str(source_mesh))
        if source_mesh != output_obj_path:
            output_obj_path.write_bytes(source_mesh.read_bytes())
    elif resolved_backend == "BPY":
        preprocess_mesh_with_bpy(
            source_mesh,
            output_obj_path,
            symmetry_x=symmetry_x,
            symmetry_y=symmetry_y,
            symmetry_z=symmetry_z,
            decimate_enabled=decimate_enabled,
            decimate_target_faces=decimate_target_faces,
            decimate_ratio=decimate_ratio,
        )
        vertices, faces = parse_obj_payload(str(output_obj_path))
    else:
        vertices, faces = load_triangle_mesh_with_trimesh(source_mesh)
        write_triangle_obj(output_obj_path, vertices, faces)
        vertices, faces = mesh_arrays_to_lists(vertices, faces)

    metadata["face_count"] = str(len(faces))
    metadata["vertex_count"] = str(len(vertices))

    mesh_artifact = build_mesh_artifact(
        obj_path=str(output_obj_path),
        vertices=vertices,
        faces=faces,
        workspace_dir=str(workspace_dir),
        source_path=str(source_mesh) if source_mesh is not None else "",
        backend=resolved_backend,
        label=stem,
        metadata=metadata,
    )
    return output_obj_path, workspace_dir, mesh_artifact
