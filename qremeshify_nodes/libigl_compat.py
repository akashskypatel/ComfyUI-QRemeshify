"""Compatibility helpers for libigl Python binding variants."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .errors import QRemeshifyError


def require_igl():
    """Require libigl to be installed."""
    try:
        import igl
    except ImportError as exc:  # pragma: no cover
        raise QRemeshifyError(
            "backend='LIBIGL' requires the 'libigl' Python package to be installed"
        ) from exc
    return igl


def libigl_write_obj_available() -> bool:
    """Return True if any supported libigl OBJ writer exists."""
    try:
        igl = require_igl()
    except QRemeshifyError:
        return False
    return hasattr(igl, "write_obj") or hasattr(igl, "writeOBJ")


def write_triangle_obj_with_libigl(
    obj_path: Path, vertices: np.ndarray, faces: np.ndarray
) -> None:
    """Write a triangle mesh to OBJ using the available libigl binding name."""
    igl = require_igl()
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)

    if hasattr(igl, "write_obj"):
        written = igl.write_obj(str(obj_path), vertices, faces)
    elif hasattr(igl, "writeOBJ"):
        written = igl.writeOBJ(str(obj_path), vertices, faces)
    else:  # pragma: no cover
        raise QRemeshifyError(
            "backend='LIBIGL' requires a libigl build that exposes write_obj or writeOBJ"
        )

    if written is False:
        raise QRemeshifyError(f"libigl could not write OBJ output: {obj_path}")
