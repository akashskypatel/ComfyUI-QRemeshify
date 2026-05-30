"""ComfyUI-QRemeshify custom nodes."""

from comfy_api.latest import IO, ComfyExtension
from typing_extensions import override

from .qremeshify_nodes.bpy_smoke_test_node import QRemeshifyBpySmokeTest
from .qremeshify_nodes import (
    QRemeshifyGenerateSharpFeatures,
    QRemeshifyMeshToOBJ,
    QRemeshifyPreprocessMesh,
    QRemeshifyOBJ,
)


class QRemeshifyExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[IO.ComfyNode]]:
        return [
            QRemeshifyBpySmokeTest,
            QRemeshifyGenerateSharpFeatures,
            QRemeshifyMeshToOBJ,
            QRemeshifyPreprocessMesh,
            QRemeshifyOBJ,
        ]


async def comfy_entrypoint() -> QRemeshifyExtension:
    """ComfyUI calls this to load your extension and its nodes."""
    return QRemeshifyExtension()
