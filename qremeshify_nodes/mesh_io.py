"""Mesh IO helpers for QRemeshify ComfyUI nodes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from .errors import QRemeshifyError


def parse_float_list(value: str, expected_count: int, label: str) -> list[float]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) != expected_count:
        raise QRemeshifyError(
            f"{label} must contain exactly {expected_count} comma-separated values"
        )
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise QRemeshifyError(f"{label} contains a non-numeric value") from exc


def prepare_output_workspace(output_dir: str, prefix: str = "qremeshify_") -> Path:
    if output_dir.strip():
        workspace_dir = Path(output_dir).expanduser().resolve()
        workspace_dir.mkdir(parents=True, exist_ok=True)
    else:
        workspace_dir = Path(tempfile.mkdtemp(prefix=prefix))
    return workspace_dir


def resolve_input_mesh_path(input_path: str) -> Path:
    raw_path = Path(input_path).expanduser()
    direct_candidate = raw_path.resolve()
    if direct_candidate.exists():
        return direct_candidate

    try:
        import folder_paths  # type: ignore
    except ImportError:
        folder_paths = None

    fallback_candidates: list[Path] = []
    if folder_paths is not None:
        input_dir = Path(folder_paths.get_input_directory()).expanduser().resolve()
        if not raw_path.is_absolute():
            fallback_candidates.append((input_dir / raw_path).resolve())
        else:
            try:
                base_dir = input_dir.parent
                relative_tail = raw_path.resolve(strict=False).relative_to(base_dir)
                fallback_candidates.append((input_dir / relative_tail).resolve())
            except ValueError:
                pass

    if raw_path.is_absolute():
        unresolved_absolute = raw_path.resolve(strict=False)
        for parent in unresolved_absolute.parents:
            try:
                relative_tail = unresolved_absolute.relative_to(parent)
            except ValueError:
                continue
            fallback_candidates.append((parent / "input" / relative_tail).resolve())

    for candidate in fallback_candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(direct_candidate)


def prepare_workspace(input_obj: str, output_dir: str) -> tuple[Path, Path]:
    source_path = resolve_input_mesh_path(input_obj)
    if source_path.suffix.lower() != ".obj":
        raise QRemeshifyError("Only OBJ input is supported by this node")

    workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_")
    working_obj = workspace_dir / source_path.name
    if source_path != working_obj:
        shutil.copyfile(source_path, working_obj)
    return workspace_dir, working_obj


def prepare_mesh_workspace(
    input_mesh: str, output_dir: str, prefix: str = "qremeshify_"
) -> tuple[Path, Path]:
    source_path = resolve_input_mesh_path(input_mesh)
    workspace_dir = prepare_output_workspace(output_dir, prefix=prefix)
    return workspace_dir, source_path


def write_triangle_obj(obj_path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    with obj_path.open("w", encoding="utf-8") as handle:
        handle.write("# OBJ file\n")
        for vertex in vertices:
            handle.write(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
        for face in faces:
            handle.write(
                f"f {int(face[0]) + 1} {int(face[1]) + 1} {int(face[2]) + 1}\n"
            )


def compute_face_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    normals[valid] /= lengths[valid][:, None]
    normals[~valid] = 0.0
    return normals


def load_triangle_mesh_with_trimesh(mesh_path: Path) -> tuple[np.ndarray, np.ndarray]:
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError(
            "This node requires the 'trimesh' Python package to be installed"
        ) from exc

    loaded = trimesh.load_mesh(str(mesh_path), process=False)
    if isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise QRemeshifyError(f"No mesh geometry found in: {mesh_path}")
        meshes = [
            geometry
            for geometry in loaded.geometry.values()
            if isinstance(geometry, trimesh.Trimesh)
        ]
        if not meshes:
            raise QRemeshifyError(f"No triangular mesh geometry found in: {mesh_path}")
        mesh = trimesh.util.concatenate(meshes)
    else:
        mesh = loaded

    if not isinstance(mesh, trimesh.Trimesh):
        raise QRemeshifyError(f"Unsupported mesh type loaded from: {mesh_path}")

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if vertices.size == 0 or faces.size == 0:
        raise QRemeshifyError(f"Mesh has no usable faces: {mesh_path}")

    return vertices, faces
