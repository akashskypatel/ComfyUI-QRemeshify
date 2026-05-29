"""Dedicated sharp-feature generation node."""

from pathlib import Path

from comfy_api.latest import IO

from .artifacts import (
    MESH_ARTIFACT_TYPE,
    SHARP_ARTIFACT_TYPE,
    build_mesh_artifact,
    build_sharp_artifact,
    parse_obj_payload,
    parse_sharp_payload,
)
from .blender_backend import bpy_available
from .constants import NODE_CATEGORY
from .mesh_to_obj_node import QRemeshifyMeshToOBJ
from .sharp_features import generate_sharp_features


class QRemeshifyGenerateSharpFeatures(IO.ComfyNode):
    """Generate a QRemeshify .sharp file from a mesh path."""

    CATEGORY = NODE_CATEGORY

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyGenerateSharpFeatures",
            display_name="QRemeshify Generate Sharp Features",
            category=cls.CATEGORY,
            inputs=[
                IO.String.Input("input_mesh", default=""),
                IO.Combo.Input(
                    "backend",
                    options=["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="AUTO",
                ),
                IO.Float.Input(
                    "sharp_angle",
                    default=35.0,
                    min=0.0,
                    max=180.0,
                    step=0.1,
                ),
                IO.String.Input("output_dir", default="", is_list=False),
                IO.String.Input("output_prefix", default="", is_list=False),
            ],
            outputs=[
                IO.String.Output(display_name="mesh_obj"),
                IO.String.Output(display_name="sharp_features_path"),
                IO.String.Output(display_name="workspace_dir"),
                IO.CustomOutput(MESH_ARTIFACT_TYPE, display_name="mesh_artifact"),
                IO.CustomOutput(SHARP_ARTIFACT_TYPE, display_name="sharp_artifact"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_mesh,
        backend,
        sharp_angle,
        output_dir="",
        output_prefix="",
        **kwargs,
    ) -> IO.NodeOutput:
        resolved_backend = backend
        if backend == "AUTO":
            resolved_backend = "BPY" if bpy_available() else "LIBIGL"
        normalization_backend = "BPY" if resolved_backend == "BPY" else "TRIMESH"
        normalized_obj_path, workspace_dir, normalized_mesh_artifact = (
            QRemeshifyMeshToOBJ().convert(
                input_mesh,
                backend=normalization_backend,
                output_dir=output_dir,
                output_prefix=output_prefix,
            )
        )
        normalized_obj_path = Path(normalized_obj_path)
        workspace_dir = Path(workspace_dir)
        stem = normalized_mesh_artifact.label or output_prefix.strip() or "mesh"
        sharp_output_path = Path(workspace_dir) / f"{stem}.sharp"
        sharp_path = generate_sharp_features(
            normalized_obj_path,
            normalized_obj_path,
            sharp_angle,
            sharp_output_path,
            resolved_backend,
        )
        vertices, faces = parse_obj_payload(str(normalized_obj_path))
        feature_rows = parse_sharp_payload(str(sharp_path))
        mesh_artifact = build_mesh_artifact(
            obj_path=str(normalized_obj_path),
            vertices=vertices,
            faces=faces,
            workspace_dir=str(workspace_dir),
            source_path=normalized_mesh_artifact.source_path,
            backend=resolved_backend,
            label=stem,
        )
        sharp_artifact = build_sharp_artifact(
            sharp_features_path=str(sharp_path),
            feature_rows=feature_rows,
            mesh_obj_path=str(normalized_obj_path),
            workspace_dir=str(workspace_dir),
            backend=resolved_backend,
            label=stem,
        )
        return IO.NodeOutput(
            str(normalized_obj_path),
            str(sharp_path),
            str(workspace_dir),
            mesh_artifact,
            sharp_artifact,
        )
