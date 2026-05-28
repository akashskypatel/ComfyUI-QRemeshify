"""ComfyUI node registration mappings."""

from .generate_sharp_node import QRemeshifyGenerateSharpFeatures
from .remesh_node import QRemeshifyOBJ

NODE_CLASS_MAPPINGS = {
    "QRemeshify Generate Sharp Features": QRemeshifyGenerateSharpFeatures,
    "QRemeshify OBJ": QRemeshifyOBJ,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QRemeshify Generate Sharp Features": "QRemeshify Generate Sharp Features",
    "QRemeshify OBJ": "QRemeshify OBJ Remesh",
}
