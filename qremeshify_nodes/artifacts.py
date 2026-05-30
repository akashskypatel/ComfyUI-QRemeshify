"""Typed ComfyUI artifacts for QRemeshify nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .mesh_io import write_triangle_obj

MESH_ARTIFACT_TYPE = "QREMESHIFY_MESH"
SHARP_ARTIFACT_TYPE = "QREMESHIFY_SHARP"


@dataclass(slots=True)
class QRemeshifyMeshArtifact:
    """Structured mesh artifact passed between ComfyUI nodes.
    
    Attributes:
        obj_path: Path to the OBJ file
        vertices: List of vertex coordinates
        faces: List of face indices
        workspace_dir: Workspace directory
        source_path: Source path
        backend: Backend used
        label: Label for the artifact
        metadata: Additional metadata
    """

    obj_path: str
    vertices: list[list[float]] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    workspace_dir: str = ""
    source_path: str = ""
    backend: str = ""
    label: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class QRemeshifySharpArtifact:
    """Structured sharp-feature artifact passed between ComfyUI nodes.
    
    Attributes:
        sharp_features_path: Path to the sharp features file
        feature_rows: List of feature rows
        mesh_obj_path: Path to the mesh OBJ file
        workspace_dir: Workspace directory
        backend: Backend used
        label: Label for the artifact
        metadata: Additional metadata
    """

    sharp_features_path: str
    feature_rows: list[list[int]] = field(default_factory=list)
    mesh_obj_path: str = ""
    workspace_dir: str = ""
    backend: str = ""
    label: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def build_mesh_artifact(
    obj_path: str,
    vertices: list[list[float]] | None = None,
    faces: list[list[int]] | None = None,
    workspace_dir: str = "",
    source_path: str = "",
    backend: str = "",
    label: str = "",
    metadata: dict[str, str] | None = None,
) -> QRemeshifyMeshArtifact:
    """
    Build a mesh artifact for ComfyUI.
    
    Args:
        obj_path: Path to the OBJ file
        vertices: List of vertex coordinates
        faces: List of face indices
        workspace_dir: Workspace directory
        source_path: Source path
        backend: Backend used
        label: Label for the artifact
        metadata: Additional metadata
        
    Returns:
        QRemeshifyMeshArtifact: Structured mesh artifact
    """
    return QRemeshifyMeshArtifact(
        obj_path=obj_path,
        vertices=vertices or [],
        faces=faces or [],
        workspace_dir=workspace_dir,
        source_path=source_path,
        backend=backend,
        label=label,
        metadata=metadata or {},
    )


def build_sharp_artifact(
    sharp_features_path: str,
    feature_rows: list[list[int]] | None = None,
    mesh_obj_path: str = "",
    workspace_dir: str = "",
    backend: str = "",
    label: str = "",
    metadata: dict[str, str] | None = None,
) -> QRemeshifySharpArtifact:
    """
    Build a sharp-feature artifact for ComfyUI.
    
    Args:
        sharp_features_path: Path to the sharp features file
        feature_rows: List of feature rows
        mesh_obj_path: Path to the mesh OBJ file
        workspace_dir: Workspace directory
        backend: Backend used
        label: Label for the artifact
        metadata: Additional metadata
        
    Returns:
        QRemeshifySharpArtifact: Structured sharp-feature artifact
    """
    return QRemeshifySharpArtifact(
        sharp_features_path=sharp_features_path,
        feature_rows=feature_rows or [],
        mesh_obj_path=mesh_obj_path,
        workspace_dir=workspace_dir,
        backend=backend,
        label=label,
        metadata=metadata or {},
    )


def resolve_mesh_input(
    input_obj: str, mesh_artifact: QRemeshifyMeshArtifact | None
) -> str:
    """
    Resolve mesh path from artifact or direct input.
    
    Args:
        input_obj: Direct mesh path
        mesh_artifact: Mesh artifact
        
    Returns:
        str: Resolved mesh path
    """
    if mesh_artifact is not None and mesh_artifact.obj_path:
        return mesh_artifact.obj_path
    return input_obj


def resolve_sharp_input(
    sharp_features_path: str,
    sharp_artifact: QRemeshifySharpArtifact | None,
) -> str:
    """
    Resolve sharp features path from artifact or direct input.
    
    Args:
        sharp_features_path: Direct sharp features path
        sharp_artifact: Sharp features artifact
        
    Returns:
        str: Resolved sharp features path
    """
    if sharp_artifact is not None and sharp_artifact.sharp_features_path:
        return sharp_artifact.sharp_features_path
    return sharp_features_path


def materialize_mesh_artifact(
    mesh_artifact: QRemeshifyMeshArtifact, target_path: str
) -> str:
    """
    Materialize mesh artifact to target path.
    
    Args:
        mesh_artifact: Mesh artifact to materialize
        target_path: Target path for the mesh
        
    Returns:
        str: Path to the materialized mesh
    """
    if mesh_artifact.vertices and mesh_artifact.faces:
        vertices = np.asarray(mesh_artifact.vertices, dtype=np.float64)
        faces = np.asarray(mesh_artifact.faces, dtype=np.int64)
        write_triangle_obj(Path(target_path), vertices, faces)
        return target_path
    if mesh_artifact.obj_path:
        source = Path(mesh_artifact.obj_path).expanduser().resolve()
        destination = Path(target_path)
        if source != destination:
            destination.write_bytes(source.read_bytes())
        return str(destination)
    raise ValueError("Mesh artifact does not contain materializable payloads")


def materialize_sharp_artifact(
    sharp_artifact: QRemeshifySharpArtifact, target_path: str
) -> str:
    """
    Materialize sharp artifact to target path.
    
    Args:
        sharp_artifact: Sharp artifact to materialize
        target_path: Target path for the sharp features
        
    Returns:
        str: Path to the materialized sharp features
    """
    if sharp_artifact.feature_rows:
        destination = Path(target_path)
        with destination.open("w", encoding="utf-8") as handle:
            handle.write(f"{len(sharp_artifact.feature_rows)}\n")
            for row in sharp_artifact.feature_rows:
                handle.write(f"{int(row[0])},{int(row[1])},{int(row[2])}\n")
        return str(destination)
    if sharp_artifact.sharp_features_path:
        source = Path(sharp_artifact.sharp_features_path).expanduser().resolve()
        destination = Path(target_path)
        if source != destination:
            destination.write_bytes(source.read_bytes())
        return str(destination)
    raise ValueError("Sharp artifact does not contain materializable payloads")


def parse_obj_payload(obj_path: str) -> tuple[list[list[float]], list[list[int]]]:
    """
    Parse OBJ file to extract vertices and faces.
    
    Args:
        obj_path: Path to the OBJ file
        
    Returns:
        tuple[list[list[float]], list[list[int]]]: Vertices and faces
    """
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    for line in (
        Path(obj_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    ):
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif line.startswith("f "):
            face: list[int] = []
            for token in line.split()[1:]:
                vertex_token = token.split("/")[0]
                if vertex_token:
                    face.append(int(vertex_token) - 1)
            if face:
                faces.append(face)
    return vertices, faces


def parse_sharp_payload(sharp_path: str) -> list[list[int]]:
    """
    Parse sharp features file to extract feature rows.
    
    Args:
        sharp_path: Path to the sharp features file
        
    Returns:
        list[list[int]]: List of feature rows
    """
    rows: list[list[int]] = []
    lines = Path(sharp_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            rows.append([int(parts[0]), int(parts[1]), int(parts[2])])
    return rows


def mesh_arrays_to_lists(
    vertices: np.ndarray, faces: np.ndarray
) -> tuple[list[list[float]], list[list[int]]]:
    """
    Convert numpy arrays to lists for artifact storage.
    
    Args:
        vertices: Numpy array of vertices
        faces: Numpy array of faces
        
    Returns:
        tuple[list[list[float]], list[list[int]]]: Vertices and faces as lists
    """
    return vertices.tolist(), faces.tolist()
