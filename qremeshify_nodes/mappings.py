"""ComfyUI node registration mappings."""

from .generate_sharp_node import QRemeshifyGenerateSharpFeatures
from .mesh_to_obj_node import QRemeshifyMeshToOBJ
from .remesh_node import QRemeshifyOBJ

NODE_CLASS_MAPPINGS = {
    "QRemeshify Mesh To OBJ": QRemeshifyMeshToOBJ,
    "QRemeshify Generate Sharp Features": QRemeshifyGenerateSharpFeatures,
    "QRemeshify OBJ": QRemeshifyOBJ,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QRemeshify Mesh To OBJ": "QRemeshify Mesh To OBJ",
    "QRemeshify Generate Sharp Features": "QRemeshify Generate Sharp Features",
    "QRemeshify OBJ": "QRemeshify OBJ Remesh",
}
