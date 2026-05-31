"""Artifact payload parsing and conversion helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def parse_obj_payload(obj_path: str) -> tuple[list[list[float]], list[list[int]]]:
    """Parse OBJ file to extract vertices and faces."""
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
    """Parse sharp features file to extract feature rows."""
    rows: list[list[int]] = []
    lines = Path(sharp_path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            rows.append([int(parts[0]), int(parts[1]), int(parts[2])])
    return rows


def mesh_arrays_to_lists(
    vertices: np.ndarray, faces: np.ndarray
) -> tuple[list[list[float]], list[list[int]]]:
    """Convert numpy arrays to Python lists for artifact storage."""
    return vertices.tolist(), faces.tolist()
