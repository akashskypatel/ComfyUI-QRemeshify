"""Dedicated mesh preprocessing node."""

from comfy_api.latest import IO, Types

from .constants import NODE_CATEGORY
from .load_3d_input import SUPPORTED_3D_SUFFIXES, list_input_3d_files
from .preprocess_helpers import preprocess_mesh_input


class QRemeshifyPreprocessMesh(IO.ComfyNode):
    """Normalize and optionally preprocess a mesh before remeshing."""

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyPreprocessMesh",
            display_name="QRemeshify Preprocess Mesh",
            category=NODE_CATEGORY,
            inputs=[
                IO.MultiType.Input(
                    IO.Combo.Input(
                        "input_mesh",
                        options=["none"] + sorted(list_input_3d_files(SUPPORTED_3D_SUFFIXES)),
                        upload=IO.UploadType.model,
                    ),
                    [IO.File3DAny, IO.Mesh],
                ),
                IO.Combo.Input(
                    "backend",
                    options=["AUTO", "BPY", "TRIMESH"],
                    default="AUTO",
                ),
                IO.Boolean.Input("symmetry_x", default=False),
                IO.Boolean.Input("symmetry_y", default=False),
                IO.Boolean.Input("symmetry_z", default=False),
                IO.Boolean.Input("decimate_enabled", default=False),
                IO.Int.Input("decimate_target_faces", default=0, min=0, max=50000000, step=1),
                IO.Float.Input("decimate_ratio", default=1.0, min=0.0, max=1.0, step=0.001),
                IO.Boolean.Input("generate_sharp", default=False),
                IO.Float.Input("sharp_angle", default=35.0, min=0.0, max=180.0, step=0.1),
                IO.Combo.Input(
                    "sharp_backend",
                    options=["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="AUTO",
                ),
                IO.String.Input("output_dir", default=""),
                IO.String.Input("output_prefix", default=""),
            ],
            outputs=[
                IO.String.Output(display_name="output_obj"),
                IO.String.Output(display_name="workspace_dir"),
                IO.File3DAny.Output(display_name="model_3d"),
                IO.AnyType.Output(display_name="mesh_artifact"),
                IO.String.Output(display_name="sharp_features_path"),
                IO.AnyType.Output(display_name="sharp_artifact"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_mesh,
        backend="AUTO",
        symmetry_x=False,
        symmetry_y=False,
        symmetry_z=False,
        decimate_enabled=False,
        decimate_target_faces=0,
        decimate_ratio=1.0,
        generate_sharp=False,
        sharp_angle=35.0,
        sharp_backend="AUTO",
        output_dir="",
        output_prefix="",
        **kwargs,
    ) -> IO.NodeOutput:
        output_obj_path, workspace_dir, mesh_artifact, sharp_path, sharp_artifact = preprocess_mesh_input(
            input_mesh,
            backend=backend,
            output_dir=output_dir,
            output_prefix=output_prefix,
            symmetry_x=symmetry_x,
            symmetry_y=symmetry_y,
            symmetry_z=symmetry_z,
            decimate_enabled=decimate_enabled,
            decimate_target_faces=decimate_target_faces,
            decimate_ratio=decimate_ratio,
            generate_sharp=generate_sharp,
            sharp_angle=sharp_angle,
            sharp_backend=sharp_backend,
        )
        model_3d = Types.File3D(str(output_obj_path))
        return IO.NodeOutput(
            str(output_obj_path),
            str(workspace_dir),
            model_3d,
            mesh_artifact,
            sharp_path,
            sharp_artifact,
        )
