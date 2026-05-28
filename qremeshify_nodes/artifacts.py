"""Typed ComfyUI artifacts for QRemeshify nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


MESH_ARTIFACT_TYPE = "QREMESHIFY_MESH"
SHARP_ARTIFACT_TYPE = "QREMESHIFY_SHARP"


@dataclass(slots=True)
class QRemeshifyMeshArtifact:
    """Structured mesh artifact passed between ComfyUI nodes."""

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
    """Structured sharp-feature artifact passed between ComfyUI nodes."""

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
    return QRemeshifySharpArtifact(
        sharp_features_path=sharp_features_path,
        feature_rows=feature_rows or [],
        mesh_obj_path=mesh_obj_path,
        workspace_dir=workspace_dir,
        backend=backend,
        label=label,
        metadata=metadata or {},
    )


def resolve_mesh_input(input_obj: str, mesh_artifact: QRemeshifyMeshArtifact | None) -> str:
    if mesh_artifact is not None and mesh_artifact.obj_path:
        return mesh_artifact.obj_path
    return input_obj


def resolve_sharp_input(
    sharp_features_path: str,
    sharp_artifact: QRemeshifySharpArtifact | None,
) -> str:
    if sharp_artifact is not None and sharp_artifact.sharp_features_path:
        return sharp_artifact.sharp_features_path
    return sharp_features_path


def parse_obj_payload(obj_path: str) -> tuple[list[list[float]], list[list[int]]]:
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    for line in Path(obj_path).read_text(encoding="utf-8", errors="ignore").splitlines():
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
    rows: list[list[int]] = []
    lines = Path(sharp_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            rows.append([int(parts[0]), int(parts[1]), int(parts[2])])
    return rows


def mesh_arrays_to_lists(vertices: np.ndarray, faces: np.ndarray) -> tuple[list[list[float]], list[list[int]]]:
    return vertices.tolist(), faces.tolist()
