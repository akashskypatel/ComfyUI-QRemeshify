"""Shared helpers for ComfyUI 3D file selection inputs."""

from __future__ import annotations

import os
from pathlib import Path

import folder_paths
import nodes

SUPPORTED_3D_SUFFIXES = {
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


def normalize_path(path: str) -> str:
    """Normalize path separators to forward slashes.
    
    Args:
        path: Path string to normalize
        
    Returns:
        Normalized path string
    """
    return path.replace("\\", "/")


def list_input_3d_files(
    allowed_suffixes: set[str] | None = None,
) -> list[str]:
    """List all 3D files in the input/3d directory.
    
    Args:
        allowed_suffixes: Set of allowed file suffixes
        
    Returns:
        List of normalized file paths
    """
    input_dir = os.path.join(folder_paths.get_input_directory(), "3d")
    os.makedirs(input_dir, exist_ok=True)

    input_path = Path(input_dir)
    base_path = Path(folder_paths.get_input_directory())
    suffixes = allowed_suffixes or SUPPORTED_3D_SUFFIXES
    return [
        normalize_path(str(file_path.relative_to(base_path)))
        for file_path in input_path.rglob("*")
        if file_path.suffix.lower() in suffixes
    ]


def resolve_selected_model_path(model_file: str) -> Path | None:
    """Resolve selected model path from file path.
    
    Args:
        model_file: File path string
        
    Returns:
        Resolved Path object or None
    """
    if not model_file or model_file == "none":
        return None
    return Path(folder_paths.get_annotated_filepath(model_file))


def resolve_model_path_or_selected(value: str) -> Path | None:
    """Resolve model path or selected model path.
    
    Args:
        value: File path string
        
    Returns:
        Resolved Path object or None
    """
    if not value or value == "none":
        return None

    candidate = Path(value).expanduser()
    if candidate.exists():
        return candidate.resolve()

    return resolve_selected_model_path(value)


def preload_load3d_images(image) -> None:
    """Preload load3d images.
    
    Args:
        image: Image dictionary
    """
    if not image or not isinstance(image, dict):
        return

    image_keys = ["image", "mask", "normal"]
    if not all(key in image for key in image_keys):
        return

    load_image_node = nodes.LoadImage()
    for key in image_keys:
        image_path = folder_paths.get_annotated_filepath(image[key])
        load_image_node.load_image(image=image_path)
