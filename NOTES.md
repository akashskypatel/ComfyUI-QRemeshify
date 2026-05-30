# Notes

Developer-facing implementation notes, environment-specific findings, and lower-level operational details live here instead of in the user-facing README.

## Environment Findings
- In the currently validated environment, the installed `libigl` package does not expose `igl.sharp_edges`.
- Because of that, strict `sharp_backend="LIBIGL"` is not usable in that environment unless the installed libigl build changes.
- `TRIMESH` decimation depends on trimesh quadric-decimation support being installed and working in the active Python environment. In practice this typically requires `fast-simplification`.

## Output Semantics
- `model_3d` outputs are typed `FILE_3D` wrappers around generated OBJ paths.
- Generated OBJ files are written into the node workspace or user-supplied `output_dir`; they are not copied into a dedicated extension-managed `3d` folder.

## Artifact Contract Details
- Internal helpers still accept path strings for compatibility with artifact materialization and internal calls, even though the primary user-facing socket contract for preprocess and mesh-to-OBJ nodes is `FILE_3D` / `MESH`.

Actual artifact fields:
- mesh artifact:
  - `obj_path`
  - `vertices`
  - `faces`
  - `workspace_dir`
  - `source_path`
  - `backend`
  - `label`
  - `metadata`
- sharp artifact:
  - `sharp_features_path`
  - `feature_rows`
  - `mesh_obj_path`
  - `workspace_dir`
  - `backend`
  - `label`
  - `metadata`

## libigl Notes
- `LIBIGL` decimation checks manifoldness with:
  - `igl.is_edge_manifold(F)`
  - `igl.is_vertex_manifold(F)`
- `igl.bfs_orient(F)` is available in the installed bindings but is not currently used as an automatic repair step.

## Cache Note
- `use_cache=true` only skips remesh/trace when the expected traced intermediate already exists in the chosen `output_dir`.

## Limitations
- The backend contract is still OBJ / `.sharp` file-based internally even though node-to-node contracts can now use richer artifacts
- Blender-backed preprocessing requires `bpy` to be installed in the exact Python environment ComfyUI is using
- Sharp-feature generation depends on the selected backend being available in the same Python environment ComfyUI is using
- Convexity inference in the generated `.sharp` file may need refinement for meshes with inconsistent winding