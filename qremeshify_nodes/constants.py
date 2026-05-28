"""Shared constants for QRemeshify ComfyUI nodes."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "qremesh_backend"
CONFIG_DIR = ROOT_DIR / "qremeshify_config"
NODE_CATEGORY = "mesh/remesh"

FLOW_CONFIG_FILES = {
    "SIMPLE": "main_config/flow_virtual_simple.json",
    "HALF": "main_config/flow_virtual_half.json",
}

SATSUMA_CONFIG_FILES = {
    "DEFAULT": "satsuma/default.json",
    "MST": "satsuma/approx-mst.json",
    "ROUND2EVEN": "satsuma/approx-round2even.json",
    "SYMMDC": "satsuma/approx-symmdc.json",
    "EDGETHRU": "satsuma/edgethru.json",
    "LEMON": "satsuma/lemon.json",
    "NODETHRU": "satsuma/nodethru.json",
}

ILP_METHODS = {
    "LEASTSQUARES": 1,
    "ABS": 2,
}
