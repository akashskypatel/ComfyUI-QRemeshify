"""Artifact materialization helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .artifact_models import QRemeshifyMeshArtifact, QRemeshifySharpArtifact
from .mesh_io import write_triangle_obj


def materialize_mesh_artifact(
    mesh_artifact: QRemeshifyMeshArtifact, target_path: str
) -> str:
    """Materialize mesh artifact to a target path."""
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
    """Materialize sharp artifact to a target path."""
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
