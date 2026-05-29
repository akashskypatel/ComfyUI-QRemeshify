"""Mesh-to-OBJ conversion node."""

from pathlib import Path

import numpy as np
from comfy_api.latest import IO

from .artifacts import (
    MESH_ARTIFACT_TYPE,
    build_mesh_artifact,
    mesh_arrays_to_lists,
    parse_obj_payload,
)
from .blender_backend import bpy_available, normalize_mesh_to_obj_with_bpy
from .constants import NODE_CATEGORY
from .errors import QRemeshifyError
from .mesh_io import (
    load_triangle_mesh_with_trimesh,
    prepare_mesh_workspace,
    prepare_output_workspace,
    write_triangle_obj,
)


def _to_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    return np.asarray(value)


def _extract_mesh_arrays(mesh_value):
    vertices = _to_numpy(mesh_value.vertices)
    faces = _to_numpy(mesh_value.faces)

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
        vertex_counts = _to_numpy(vertex_counts).reshape(-1)
        if vertex_counts.size != 1:
            raise QRemeshifyError("MESH input must contain exactly one mesh item")
        vertices = vertices[: int(vertex_counts[0])]
    if face_counts is not None:
        face_counts = _to_numpy(face_counts).reshape(-1)
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


def _coerce_mesh_input(input_mesh, output_dir: str, output_prefix: str):
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


class QRemeshifyMeshToOBJ(IO.ComfyNode):
    """Convert a mesh file to an OBJ suitable for downstream nodes."""

    CATEGORY = NODE_CATEGORY

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyMeshToOBJ",
            display_name="QRemeshify Mesh to OBJ",
            category=cls.CATEGORY,
            inputs=[
                IO.String.Input("input_mesh", default=""),
                IO.Combo.Input(
                    "backend",
                    options=["AUTO", "BPY", "TRIMESH"],
                    default="AUTO",
                ),
                IO.String.Input("output_dir", default="", is_list=False),
                IO.String.Input("output_prefix", default="", is_list=False),
            ],
            outputs=[
                IO.String.Output(display_name="output_obj"),
                IO.String.Output(display_name="workspace_dir"),
                IO.CustomOutput(MESH_ARTIFACT_TYPE, display_name="mesh_artifact"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_mesh,
        backend="AUTO",
        output_dir="",
        output_prefix="",
        **kwargs,
    ) -> IO.NodeOutput:
        workspace_dir, source_mesh, stem, input_kind = _coerce_mesh_input(
            input_mesh, output_dir, output_prefix
        )
        output_obj_path = workspace_dir / f"{stem}.obj"

        resolved_backend = backend
        if backend == "AUTO":
            resolved_backend = "BPY" if bpy_available() else "TRIMESH"

        if input_kind == "mesh":
            vertices, faces = _extract_mesh_arrays(input_mesh)
            write_triangle_obj(output_obj_path, vertices, faces)
            vertices, faces = mesh_arrays_to_lists(vertices, faces)
        elif source_mesh.suffix.lower() == ".obj":
            if source_mesh != output_obj_path:
                output_obj_path.write_bytes(source_mesh.read_bytes())
            vertices, faces = parse_obj_payload(str(output_obj_path))
        elif resolved_backend == "BPY":
            normalize_mesh_to_obj_with_bpy(source_mesh, output_obj_path)
            vertices, faces = parse_obj_payload(str(output_obj_path))
        else:
            vertices, faces = load_triangle_mesh_with_trimesh(source_mesh)
            write_triangle_obj(output_obj_path, vertices, faces)
            vertices, faces = mesh_arrays_to_lists(vertices, faces)

        mesh_artifact = build_mesh_artifact(
            obj_path=str(output_obj_path),
            vertices=vertices,
            faces=faces,
            workspace_dir=str(workspace_dir),
            source_path=str(source_mesh) if source_mesh is not None else "",
            backend=resolved_backend,
            label=stem,
        )
        return IO.NodeOutput(
            str(output_obj_path),
            str(workspace_dir),
            mesh_artifact,
        )
