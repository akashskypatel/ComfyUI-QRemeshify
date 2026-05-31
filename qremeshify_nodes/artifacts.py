"""Compatibility facade for artifact models, parsers, and materializers."""

from .artifact_materialize import (
    materialize_mesh_artifact,
    materialize_sharp_artifact,
)
from .artifact_models import (
    MESH_ARTIFACT_TYPE,
    SHARP_ARTIFACT_TYPE,
    QRemeshifyMeshArtifact,
    QRemeshifySharpArtifact,
    build_mesh_artifact,
    build_sharp_artifact,
    resolve_mesh_input,
    resolve_sharp_input,
)
from .artifact_payloads import (
    mesh_arrays_to_lists,
    parse_obj_payload,
    parse_sharp_payload,
)
