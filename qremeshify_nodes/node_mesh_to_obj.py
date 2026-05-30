"""Mesh-to-OBJ conversion node."""

from comfy_api.latest import IO

from .constants import NODE_CATEGORY
from .load_3d_input import (
    SUPPORTED_3D_SUFFIXES,
    list_input_3d_files,
)
from .preprocess_helpers import preprocess_mesh_input


class QRemeshifyMeshToOBJ(IO.ComfyNode):
    """Convert a mesh file to an OBJ suitable for downstream nodes."""

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyMeshToOBJ",
            display_name="QRemeshify Mesh to OBJ",
            category=NODE_CATEGORY,
            description="Convert a mesh file to an OBJ suitable for downstream nodes.",
            inputs=[
                IO.MultiType.Input(
                    IO.Combo.Input(
                        "input_mesh",
                        options=["none"] + sorted(list_input_3d_files(SUPPORTED_3D_SUFFIXES)),
                        upload=IO.UploadType.model,
                        tooltip="Select a mesh file to convert",
                    ),
                    [IO.File3DAny, IO.Mesh],
                ),
                IO.Combo.Input(
                    "backend",
                    options=["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="AUTO",
                    tooltip="Backend to use for mesh processing",
                ),
                IO.Boolean.Input("allow_backend_fallback", default=False, tooltip="Allow backend fallback"),
                IO.String.Input("output_dir", default="", tooltip="Output directory for converted files"),
                IO.String.Input("output_prefix", default="", tooltip="Prefix for output filenames"),
            ],
            outputs=[
                IO.String.Output(display_name="output_obj", tooltip="Output OBJ mesh file path"),
                IO.String.Output(display_name="workspace_dir", tooltip="Workspace directory path"),
                IO.AnyType.Output(display_name="mesh_artifact", tooltip="Output in-memory mesh artifact"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_mesh,
        backend="AUTO",
        allow_backend_fallback=False,
        output_dir="",
        output_prefix="",
        **kwargs,
    ) -> IO.NodeOutput:
        output_obj_path, workspace_dir, mesh_artifact, _, _, _ = preprocess_mesh_input(
            input_mesh,
            backend=backend,
            allow_backend_fallback=allow_backend_fallback,
            output_dir=output_dir,
            output_prefix=output_prefix,
        )
        return IO.NodeOutput(
            str(output_obj_path),
            str(workspace_dir),
            mesh_artifact,
        )
