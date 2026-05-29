"""ComfyUI-QRemeshify custom nodes."""

from comfy_api.latest import IO, ComfyExtension
from typing_extensions import override

from .qremeshify_nodes import (
    QRemeshifyGenerateSharpFeatures,
    QRemeshifyLoad3D,
    QRemeshifyMeshToOBJ,
    QRemeshifyOBJ,
)


class QRemeshifyExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[IO.ComfyNode]]:
        return [
            QRemeshifyGenerateSharpFeatures,
            QRemeshifyLoad3D,
            QRemeshifyMeshToOBJ,
            QRemeshifyOBJ,
        ]


async def comfy_entrypoint() -> QRemeshifyExtension:
    """ComfyUI calls this to load your extension and its nodes."""
    return QRemeshifyExtension()
