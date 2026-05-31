"""Thin facade over isolated BPY subprocess operations."""

from __future__ import annotations

from pathlib import Path


def bpy_available() -> bool:
    """Check if Blender is available via the isolated subprocess worker."""
    from .bpy_subprocess import bpy_available_via_subprocess

    return bpy_available_via_subprocess()


def normalize_mesh_to_obj_with_bpy(mesh_path: Path, output_obj_path: Path) -> Path:
    """Normalize mesh to OBJ using the BPY subprocess worker."""
    from .bpy_subprocess import normalize_mesh_to_obj_with_bpy_subprocess

    return normalize_mesh_to_obj_with_bpy_subprocess(mesh_path, output_obj_path)


def preprocess_mesh_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool = False,
    symmetry_y: bool = False,
    symmetry_z: bool = False,
    decimate_enabled: bool = False,
    decimate_target_faces: int = 0,
    decimate_ratio: float = 1.0,
    tolerance: float = 1e-5,
) -> Path:
    """Preprocess mesh using the BPY subprocess worker."""
    from .bpy_subprocess import preprocess_mesh_with_bpy_subprocess

    return preprocess_mesh_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x=symmetry_x,
        symmetry_y=symmetry_y,
        symmetry_z=symmetry_z,
        decimate_enabled=decimate_enabled,
        decimate_target_faces=decimate_target_faces,
        decimate_ratio=decimate_ratio,
        tolerance=tolerance,
    )


def preprocess_obj_with_symmetry_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    """Preprocess OBJ symmetry using the BPY subprocess worker."""
    from .bpy_subprocess import preprocess_obj_with_symmetry_with_bpy_subprocess

    return preprocess_obj_with_symmetry_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x,
        symmetry_y,
        symmetry_z,
        tolerance,
    )


def normalize_mesh_and_generate_sharp_with_bpy(
    mesh_path: Path,
    normalized_obj_path: Path,
    sharp_angle: float,
    output_path: Path,
) -> Path:
    """Normalize mesh and generate sharp features using the BPY subprocess worker."""
    from .bpy_subprocess import normalize_mesh_and_generate_sharp_with_bpy_subprocess

    return normalize_mesh_and_generate_sharp_with_bpy_subprocess(
        mesh_path,
        normalized_obj_path,
        sharp_angle,
        output_path,
    )


def postprocess_obj_with_symmetry_with_bpy(
    mesh_path: Path,
    output_obj_path: Path,
    symmetry_x: bool,
    symmetry_y: bool,
    symmetry_z: bool,
    tolerance: float = 1e-5,
) -> Path:
    """Postprocess OBJ symmetry using the BPY subprocess worker."""
    from .bpy_subprocess import postprocess_obj_with_symmetry_with_bpy_subprocess

    return postprocess_obj_with_symmetry_with_bpy_subprocess(
        mesh_path,
        output_obj_path,
        symmetry_x,
        symmetry_y,
        symmetry_z,
        tolerance,
    )
