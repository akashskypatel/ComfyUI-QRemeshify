"""Typed ComfyUI artifacts for QRemeshify nodes."""

from __future__ import annotations

from dataclasses import dataclass, field


MESH_ARTIFACT_TYPE = "QREMESHIFY_MESH"
SHARP_ARTIFACT_TYPE = "QREMESHIFY_SHARP"


@dataclass(slots=True)
class QRemeshifyMeshArtifact:
    """Structured mesh artifact passed between ComfyUI nodes."""

    obj_path: str
    workspace_dir: str = ""
    source_path: str = ""
    backend: str = ""
    label: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class QRemeshifySharpArtifact:
    """Structured sharp-feature artifact passed between ComfyUI nodes."""

    sharp_features_path: str
    mesh_obj_path: str = ""
    workspace_dir: str = ""
    backend: str = ""
    label: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def build_mesh_artifact(
    obj_path: str,
    workspace_dir: str = "",
    source_path: str = "",
    backend: str = "",
    label: str = "",
    metadata: dict[str, str] | None = None,
) -> QRemeshifyMeshArtifact:
    return QRemeshifyMeshArtifact(
        obj_path=obj_path,
        workspace_dir=workspace_dir,
        source_path=source_path,
        backend=backend,
        label=label,
        metadata=metadata or {},
    )


def build_sharp_artifact(
    sharp_features_path: str,
    mesh_obj_path: str = "",
    workspace_dir: str = "",
    backend: str = "",
    label: str = "",
    metadata: dict[str, str] | None = None,
) -> QRemeshifySharpArtifact:
    return QRemeshifySharpArtifact(
        sharp_features_path=sharp_features_path,
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
