# ComfyUI-QRemeshify

ComfyUI custom nodes for running the QRemeshify remeshing pipeline from Python, using the bundled `qremesh_backend` DLLs.

This project is based on [QRemeshify](https://github.com/ksami/QRemeshify), which is itself based on [QuadWild with Bi-MDF solver](https://github.com/cgg-bern/quadwild-bimdf) and [QuadWild](https://github.com/nicopietroni/quadwild).

# What It Does
- Runs the native QRemeshify backend from ComfyUI
- Produces quad-oriented remeshed OBJ output
- Exposes a dedicated sharp-feature generation node
- Supports `BPY`, `LIBIGL`, and `TRIMESH` backends for preprocessing and generating `.sharp` files
- Uses extension-owned runtime config files under `qremeshify_config` for advanced solver settings

# Included Nodes
## `QRemeshify Mesh To OBJ`
Converts a mesh path into an OBJ file for downstream QRemeshify nodes.

Behavior:
- if the input is already `.obj`, it is copied into the node workspace
- otherwise the mesh is normalized into a triangle OBJ through the selected backend

Inputs:
- `input_mesh`: path to the source mesh
- `backend`: `AUTO`, `BPY`, or `TRIMESH`
- `output_dir` optional
- `output_prefix` optional

Outputs:
- `output_obj`
- `workspace_dir`

## `QRemeshify Generate Sharp Features`
Preprocesses a mesh into:
- a normalized triangle OBJ
- a QRemeshify-compatible `.sharp` file
- a workspace directory path

Inputs:
- `input_mesh`: path to the source mesh
- `backend`: `AUTO`, `BPY`, `LIBIGL`, or `TRIMESH`
- `sharp_angle`: dihedral angle threshold in degrees
- `output_dir` optional
- `output_prefix` optional

Outputs:
- `mesh_obj`
- `sharp_features_path`
- `workspace_dir`

## `QRemeshify OBJ`
Runs the actual QRemeshify backend on an OBJ file.

Inputs:
- `input_obj`: path to the OBJ to remesh
- `preprocess`
- `smooth`
- `detect_sharp`
- `sharp_angle`
- `use_cache`: reuse previously generated traced intermediates and rerun only quadrangulation
- `sharp_features_path` optional
- `sharp_backend` optional fallback if `detect_sharp=True` and no `.sharp` file is supplied
- advanced solver controls such as `alpha`, `ilp_method`, `flow_config`, and `satsuma_config`

Outputs:
- `output_obj`
- `workspace_dir`
- `remeshed_obj`
- `traced_obj`

# Recommended ComfyUI Workflow
Use either of these preprocessing paths:

1. `QRemeshify Mesh To OBJ` -> `QRemeshify OBJ`
2. `QRemeshify Generate Sharp Features` -> `QRemeshify OBJ`

For the sharp-feature workflow, wire them like this:
- `mesh_obj` -> `input_obj`
- `sharp_features_path` -> `sharp_features_path`

This is the preferred workflow because the sharp-feature node writes a normalized triangle OBJ, and the `.sharp` file indices must match the exact OBJ consumed by the backend.

If you skip the first node, `QRemeshify OBJ` can still auto-generate sharp features when:
- `detect_sharp=True`
- `sharp_features_path` is empty

Cache behavior:
- `use_cache=True` skips preprocess, sharp generation, remesh, and trace
- it reuses the existing `_rem_p0.obj` traced mesh from the same `output_dir`
- this requires a prior run with `use_cache=False` in that same `output_dir`
- `use_cache=True` requires `output_dir` to be set explicitly

`AUTO` backend behavior:
- prefers `BPY` when Blender's Python module is available
- falls back to `LIBIGL` or `TRIMESH` when `bpy` is unavailable

# Requirements
- Windows
- ComfyUI
- Python environment used by ComfyUI
- Bundled backend DLLs in `qremesh_backend`

Python packages:
- `bpy` optional but preferred for Blender-faithful preprocessing
- `libigl`
- `trimesh`
- `numpy`

Runtime assets bundled with this extension:
- `qremesh_backend` for the native DLLs
- `qremeshify_config` for solver configuration files

Install the Python dependencies into ComfyUI's environment:

```powershell
pip install -r requirements.txt
```

# Installation
1. Place this repository under `ComfyUI/custom_nodes/`
2. Install Python dependencies in the ComfyUI venv:

```powershell
pip install -r requirements.txt
```

3. Restart ComfyUI

# Mesh Format Support
The native backend currently consumes OBJ files.

Current practical support is:
- `QRemeshify Mesh To OBJ`: converts common mesh formats into OBJ through `bpy` or `trimesh`
- `QRemeshify OBJ`: OBJ input only
- `QRemeshify Generate Sharp Features`: any mesh format that the selected backend can import, then converted to normalized triangle OBJ output

That means a common pattern is:
- load `STL`, `PLY`, or another supported format in `QRemeshify Mesh To OBJ` or `QRemeshify Generate Sharp Features`
- pass the generated `mesh_obj` to `QRemeshify OBJ`

# Current Limitations
- Symmetry preprocessing/postprocessing is implemented only on the `bpy` path inside `QRemeshify OBJ`
- When symmetry is enabled, the final output OBJ is mirrored back to full form, while intermediate remesh/traced outputs remain in the pre-mirror half-mesh form
- Cache mode currently reuses the traced half/full mesh already present in the chosen `output_dir`; changing symmetry or source geometry while reusing cache can make results inconsistent
- The final backend output is currently returned as OBJ path strings, not a native in-memory mesh datatype for ComfyUI
- `QRemeshify OBJ` expects filesystem paths, not uploaded binary mesh tensors or geometry objects
- Blender-backed preprocessing requires `bpy` to be installed in the exact Python environment ComfyUI is using
- Sharp-feature generation depends on the selected backend being available in the same Python environment ComfyUI is using
- Convexity inference in the generated `.sharp` file may need refinement for meshes with inconsistent winding

# Tips
- Keep meshes reasonably sized; remeshing cost grows quickly with mesh complexity
- Starting from triangulated geometry usually gives more predictable results
- If you want sharp guidance, prefer the dedicated sharp-feature node over remesh-node auto-generation
- Preserve the generated `workspace_dir` when debugging intermediate outputs

# Pipeline
```mermaid
flowchart TD
    A[Input mesh path] --> B[QRemeshify Generate Sharp Features]
    B --> C[Normalized triangle OBJ]
    B --> D[.sharp file]
    C --> E[QRemeshify OBJ]
    D --> E
    E --> F[QuadWild preprocess and field]
    F --> G[Trace patches]
    G --> H[Quadrangulate]
    H --> I[Final OBJ output]
```
