"""Load 3D files from the '3d' input directory."""

from pathlib import Path
from typing import Any

from comfy_api.latest import IO, Types

from .artifacts import build_mesh_artifact
from .constants import NODE_CATEGORY
from .load_3d_input import (
    SUPPORTED_3D_SUFFIXES,
    list_input_3d_files,
    normalize_path,
    preload_load3d_images,
    resolve_selected_model_path,
)


class QRemeshifyLoad3D(IO.ComfyNode):
    """
    Loads 3D files from the '3d' input directory.
    """

    @classmethod
    def define_schema(cls) -> IO.Schema:
        files = list_input_3d_files(SUPPORTED_3D_SUFFIXES)
        return IO.Schema(
            node_id="QRemeshifyLoad3D",
            display_name="QRemeshify Load 3D",
            category=NODE_CATEGORY,
            description="Loads 3D files from the '3d' input directory.\n"
            "Inputs: model_file - Select a 3D model file to load\n"
            "       image - Image input for 3D processing\n"
            "       width - Width for 3D processing\n"
            "       height - Height for 3D processing\n"
            "Outputs: mesh_path - Path to the loaded mesh\n"
            "       model_3d - Loaded 3D model file from '3d' directory\n"
            "       mesh_artifact - Mesh artifact for downstream nodes",
            inputs=[
                IO.Combo.Input(
                    "model_file",
                    options=["none"] + sorted(files),
                    upload=IO.UploadType.model,
                    tooltip="Select a 3D model file to load",
                ),
                IO.Load3D.Input("image", tooltip="Image input for 3D processing"),
                IO.Int.Input("width", default=1024, min=1, max=4096, step=1, tooltip="Width for 3D processing"),
                IO.Int.Input("height", default=1024, min=1, max=4096, step=1, tooltip="Height for 3D processing"),
            ],
            outputs=[
                IO.String.Output(display_name="mesh_path", tooltip="Path to the loaded mesh"),
                IO.File3DAny.Output(display_name="model_3d", tooltip="Loaded 3D model file"),
                IO.AnyType.Output(display_name="mesh_artifact", tooltip="Mesh artifact for downstream nodes")
            ],
        )

    @classmethod
    def execute(cls, model_file, image, **kwargs) -> IO.NodeOutput:
        preload_load3d_images(image)

        file_3d = None
        mesh_path = ""
        mesh_artifact = None
        if model_file and model_file != "none":
            resolved_path = resolve_selected_model_path(model_file)
            file_3d = Types.File3D(str(resolved_path))
            mesh_path = model_file
            obj_path = str(resolved_path) if resolved_path.suffix.lower() == ".obj" else ""
            mesh_artifact = build_mesh_artifact(
                obj_path=obj_path,
                workspace_dir="",
                source_path=str(resolved_path),
                backend="LOAD3D",
                label=resolved_path.stem,
                metadata={
                    "kind": "file3d",
                    "format": resolved_path.suffix.lower().lstrip("."),
                },
            )
        return IO.NodeOutput(
            mesh_path,
            file_3d,
            mesh_artifact
        )

    @classmethod
    def fingerprint_inputs(cls, model_file="none", **kwargs) -> Any:
        if not model_file or model_file == "none":
            return ("none",)

        resolved_path = resolve_selected_model_path(model_file)
        if not resolved_path.exists():
            return ("missing", normalize_path(model_file), str(resolved_path))
        stat = resolved_path.stat()
        return (
            normalize_path(model_file),
            str(resolved_path.resolve()),
            stat.st_size,
            stat.st_mtime_ns,
        )

    process = execute
