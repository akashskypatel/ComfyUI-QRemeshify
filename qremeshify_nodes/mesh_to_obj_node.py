"""Mesh-to-OBJ conversion node."""

from .artifacts import MESH_ARTIFACT_TYPE, build_mesh_artifact, mesh_arrays_to_lists, parse_obj_payload
from .blender_backend import normalize_mesh_to_obj_with_bpy
from .blender_backend import bpy_available
from .constants import NODE_CATEGORY
from .mesh_io import load_triangle_mesh_with_trimesh, prepare_mesh_workspace, write_triangle_obj


class QRemeshifyMeshToOBJ:
    """Convert a mesh file to an OBJ suitable for downstream nodes."""

    CATEGORY = NODE_CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_mesh": ("STRING", {"default": ""}),
            },
            "optional": {
                "backend": (["AUTO", "BPY", "TRIMESH"], {"default": "AUTO"}),
                "output_dir": ("STRING", {"default": ""}),
                "output_prefix": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", MESH_ARTIFACT_TYPE)
    RETURN_NAMES = ("output_obj", "workspace_dir", "mesh_artifact")
    FUNCTION = "convert"

    def convert(self, input_mesh, backend="BPY", output_dir="", output_prefix=""):
        workspace_dir, source_mesh = prepare_mesh_workspace(
            input_mesh,
            output_dir,
            prefix="qremeshify_obj_",
        )
        stem = output_prefix.strip() or source_mesh.stem
        output_obj_path = workspace_dir / f"{stem}.obj"

        resolved_backend = backend
        if backend == "AUTO":
            resolved_backend = "BPY" if bpy_available() else "TRIMESH"

        if source_mesh.suffix.lower() == ".obj":
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
            source_path=str(source_mesh),
            backend=resolved_backend,
            label=stem,
        )
        return (str(output_obj_path), str(workspace_dir), mesh_artifact)
