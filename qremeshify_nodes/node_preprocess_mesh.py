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
            description="Normalize and optionally preprocess a mesh before remeshing. "
            "Normalizes a mesh into a triangle OBJ and can optionally: "
            "  1. Apply symmetry along X, Y, or Z axes (Only available with BPY backend)"
            "  2. Decimate the mesh to reduce face count (TRIMESH backend requires fast-simplification package to be installed)"
            "  3. Generate sharp features for better remeshing (Only available with BPY and TRIMESH backend)",
            inputs=[
                IO.MultiType.Input(
                    IO.Combo.Input(
                        "input_mesh",
                        options=["none"] + sorted(list_input_3d_files(SUPPORTED_3D_SUFFIXES)),
                        upload=IO.UploadType.model,
                        tooltip="Select a mesh file to preprocess",
                    ),
                    [IO.File3DAny, IO.Mesh],
                ),
                IO.Combo.Input(
                    "backend",
                    options=["BPY"], # disable other backends for now ["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="BPY", # "AUTO",
                    tooltip="Backend to use for mesh processing",
                ),
                IO.Boolean.Input("symmetry_x", default=False, tooltip="Apply symmetry along X axis"),
                IO.Boolean.Input("symmetry_y", default=False, tooltip="Apply symmetry along Y axis"),
                IO.Boolean.Input("symmetry_z", default=False, tooltip="Apply symmetry along Z axis"),
                IO.Boolean.Input("decimate_enabled", default=False, tooltip="Enable decimation"),
                IO.Int.Input("decimate_target_faces", default=0, min=0, max=50000000, step=1, tooltip="Target number of faces after decimation (0-50000000)"),
                IO.Float.Input("decimate_ratio", default=1.0, min=0.0, max=1.0, step=0.001, tooltip="Decimation ratio (0.0-1.0)"),
                IO.Boolean.Input("remove_degenerate_faces", default=False, tooltip="Remove degenerate or zero-area faces before further preprocessing"),
                IO.Boolean.Input("remove_duplicate_faces", default=False, tooltip="Remove duplicate faces that share the same topology"),
                IO.Boolean.Input("remove_unreferenced_vertices", default=False, tooltip="Remove vertices that are not used by any surviving face"),
                IO.Boolean.Input("merge_duplicate_vertices", default=False, tooltip="Merge near-duplicate vertices before preprocessing"),
                IO.Boolean.Input("fill_holes", default=False, tooltip="Fill mesh holes using the TRIMESH repair path; requires TRIMESH backend or backend fallback"),
                IO.Boolean.Input("allow_backend_fallback", default=False, tooltip="Allow backend fallback"),
                IO.Boolean.Input("generate_sharp", default=True, tooltip="Generate sharp features"),
                IO.Float.Input("sharp_angle", default=35.0, min=0.0, max=180.0, step=0.1, tooltip="Sharp angle threshold (0.0-180.0)"),
                IO.Combo.Input(
                    "sharp_backend",
                    options=["BPY"], # disable other backends for now ["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="BPY", # "AUTO",
                    tooltip="Backend to use for sharp feature detection",
                ),
                IO.String.Input("output_dir", default="", tooltip="Output directory for processed files"),
                IO.String.Input("output_prefix", default="", tooltip="Prefix for output filenames"),
            ],
            outputs=[
                IO.String.Output(display_name="output_obj", tooltip="Output OBJ mesh file path"),
                IO.String.Output(display_name="workspace_dir", tooltip="Workspace directory path"),
                IO.File3DAny.Output(display_name="model_3d", tooltip="Output 3D model file in '3d' directory"),
                IO.AnyType.Output(display_name="mesh_artifact", tooltip="Output in-memory mesh artifact"),
                IO.String.Output(display_name="sharp_features_path", tooltip="Sharp features file path"),
                IO.AnyType.Output(display_name="sharp_artifact", tooltip="Output in-memory sharp artifact"),
                IO.String.Output(display_name="mesh_info", tooltip="Input and output mesh stats in markdown format"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_mesh,
        backend="BPY", # "AUTO",
        symmetry_x=False,
        symmetry_y=False,
        symmetry_z=False,
        decimate_enabled=False,
        decimate_target_faces=0,
        decimate_ratio=1.0,
        remove_degenerate_faces=False,
        remove_duplicate_faces=False,
        remove_unreferenced_vertices=False,
        merge_duplicate_vertices=False,
        fill_holes=False,
        allow_backend_fallback=False,
        generate_sharp=True,
        sharp_angle=35.0,
        sharp_backend="BPY", # "AUTO",
        output_dir="",
        output_prefix="",
        **kwargs,
    ) -> IO.NodeOutput:
        (
            output_obj_path,
            workspace_dir,
            mesh_artifact,
            sharp_path,
            sharp_artifact,
            mesh_info,
        ) = preprocess_mesh_input(
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
            remove_degenerate_faces=remove_degenerate_faces,
            remove_duplicate_faces=remove_duplicate_faces,
            remove_unreferenced_vertices=remove_unreferenced_vertices,
            merge_duplicate_vertices=merge_duplicate_vertices,
            fill_holes=fill_holes,
            allow_backend_fallback=allow_backend_fallback,
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
            mesh_info,
        )
