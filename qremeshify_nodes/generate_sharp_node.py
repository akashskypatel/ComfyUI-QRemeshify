"""Dedicated sharp-feature generation node."""

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
from .mesh_io import prepare_mesh_workspace
from .sharp_features import generate_sharp_features


class QRemeshifyGenerateSharpFeatures:
    """Generate a QRemeshify .sharp file from a mesh path."""

    CATEGORY = NODE_CATEGORY

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_mesh": ("STRING", {"default": ""}),
                "backend": (["AUTO", "BPY", "LIBIGL", "TRIMESH"], {"default": "AUTO"}),
                "sharp_angle": ("FLOAT", {"default": 35.0, "min": 0.0, "max": 180.0, "step": 0.1}),
            },
            "optional": {
                "output_dir": ("STRING", {"default": ""}),
                "output_prefix": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", MESH_ARTIFACT_TYPE, SHARP_ARTIFACT_TYPE)
    RETURN_NAMES = ("mesh_obj", "sharp_features_path", "workspace_dir", "mesh_artifact", "sharp_artifact")
    FUNCTION = "generate"

    def generate(self, input_mesh, backend, sharp_angle, output_dir="", output_prefix=""):
        workspace_dir, source_mesh = prepare_mesh_workspace(input_mesh, output_dir, prefix="qremeshify_sharp_")
        stem = output_prefix.strip() or source_mesh.stem
        normalized_obj_path = workspace_dir / f"{stem}.obj"
        sharp_output_path = workspace_dir / f"{stem}.sharp"
        resolved_backend = backend
        if backend == "AUTO":
            resolved_backend = "BPY" if bpy_available() else "LIBIGL"
        sharp_path = generate_sharp_features(
            source_mesh,
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
            source_path=str(source_mesh),
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
        return (
            str(normalized_obj_path),
            str(sharp_path),
            str(workspace_dir),
            mesh_artifact,
            sharp_artifact,
        )
