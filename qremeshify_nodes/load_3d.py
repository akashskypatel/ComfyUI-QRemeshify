"""Load 3D files from the '3d' input directory."""

import os
from pathlib import Path

import folder_paths
from comfy_api.latest import IO, InputImpl, Types

import nodes


def normalize_path(path):
    return path.replace("\\", "/")


class QRemeshifyLoad3D(IO.ComfyNode):
    """
    Loads 3D files from the '3d' input directory.
    """

    @classmethod
    def define_schema(cls) -> IO.Schema:
        input_dir = os.path.join(folder_paths.get_input_directory(), "3d")

        os.makedirs(input_dir, exist_ok=True)

        input_path = Path(input_dir)
        base_path = Path(folder_paths.get_input_directory())

        files = [
            normalize_path(str(file_path.relative_to(base_path)))
            for file_path in input_path.rglob("*")
            if file_path.suffix.lower()
            in {
                ".gltf",
                ".glb",
                ".obj",
                ".fbx",
                ".stl",
                ".spz",
                ".splat",
                ".ply",
                ".ksplat",
            }
        ]
        return IO.Schema(
            node_id="QRemeshifyLoad3D",
            display_name="QRemeshify Load 3D & Animation",
            category="QRemeshify",
            essentials_category="Extensions",
            inputs=[
                IO.Combo.Input(
                    "model_file",
                    options=["none"] + sorted(files),
                    upload=IO.UploadType.model,
                ),
                IO.Load3D.Input("image"),
                IO.Int.Input("width", default=1024, min=1, max=4096, step=1),
                IO.Int.Input("height", default=1024, min=1, max=4096, step=1),
            ],
            outputs=[
                IO.Image.Output(display_name="image"),
                IO.Mask.Output(display_name="mask"),
                IO.String.Output(display_name="mesh_path"),
                IO.Image.Output(display_name="normal"),
                IO.Load3DCamera.Output(display_name="camera_info"),
                IO.Video.Output(display_name="recording_video"),
                IO.File3DAny.Output(display_name="model_3d"),
            ],
        )

    @classmethod
    def execute(cls, model_file, image, **kwargs) -> IO.NodeOutput:
        image_path = folder_paths.get_annotated_filepath(image["image"])
        mask_path = folder_paths.get_annotated_filepath(image["mask"])
        normal_path = folder_paths.get_annotated_filepath(image["normal"])

        load_image_node = nodes.LoadImage()
        output_image, ignore_mask = load_image_node.load_image(image=image_path)
        ignore_image, output_mask = load_image_node.load_image(image=mask_path)
        normal_image, ignore_mask2 = load_image_node.load_image(image=normal_path)

        video = None

        if image["recording"] != "":
            recording_video_path = folder_paths.get_annotated_filepath(
                image["recording"]
            )

            video = InputImpl.VideoFromFile(recording_video_path)

        file_3d = None
        mesh_path = ""
        if model_file and model_file != "none":
            file_3d = Types.File3D(folder_paths.get_annotated_filepath(model_file))
            mesh_path = model_file
        return IO.NodeOutput(
            output_image,
            output_mask,
            mesh_path,
            normal_image,
            image["camera_info"],
            video,
            file_3d,
        )
