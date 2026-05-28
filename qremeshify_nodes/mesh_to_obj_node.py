"""Mesh-to-OBJ conversion node."""

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
                "output_dir": ("STRING", {"default": ""}),
                "output_prefix": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("output_obj", "workspace_dir")
    FUNCTION = "convert"

    def convert(self, input_mesh, output_dir="", output_prefix=""):
        workspace_dir, source_mesh = prepare_mesh_workspace(
            input_mesh,
            output_dir,
            prefix="qremeshify_obj_",
        )
        stem = output_prefix.strip() or source_mesh.stem
        output_obj_path = workspace_dir / f"{stem}.obj"

        if source_mesh.suffix.lower() == ".obj":
            if source_mesh != output_obj_path:
                output_obj_path.write_bytes(source_mesh.read_bytes())
        else:
            vertices, faces = load_triangle_mesh_with_trimesh(source_mesh)
            write_triangle_obj(output_obj_path, vertices, faces)

        return (str(output_obj_path), str(workspace_dir))
