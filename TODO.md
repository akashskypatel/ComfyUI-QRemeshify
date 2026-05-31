# TODO

## Completed Migration Work
- [x] Add `bpy` as an optional high-fidelity preprocessing backend.
- [x] Implement first-pass symmetry preprocessing/postprocessing on the `bpy` path.
- [x] Implement cache mode in `QRemeshify OBJ` using previously generated intermediate files.
- [x] Fix the OBJ/MTL warning seen during symmetry postprocess import.
- [x] Add native in-memory ComfyUI mesh/sharp artifact datatypes so nodes can pass richer geometry objects instead of only bare path strings.
- [x] Add optional `vertices` / `faces` payloads to `QREMESHIFY_MESH` artifacts while preserving current path-backed behavior.
- [x] Add optional parsed feature-row payloads to `QREMESHIFY_SHARP` artifacts while preserving current path-backed behavior.
- [x] Populate those in-memory payloads in `QRemeshify Mesh To OBJ` and `QRemeshify Preprocess Mesh`.
- [x] Make `QRemeshify OBJ` prefer in-memory artifact payloads and only materialize OBJ / `.sharp` files at the native backend boundary.
- [x] Parse final/remeshed/traced OBJ outputs back into in-memory mesh payloads for returned mesh artifacts.
- [x] Remove the remaining non-runtime `QRemeshify` reference artifacts.
- [x] Refactor all mesh preprocessing into a dedicated `QRemeshify Preprocess Mesh` node, including normalization, symmetry operations, optional decimation, and sharp-feature generation.

## Testing And Validation
- [x] Validate the `bpy` path end-to-end inside ComfyUI's active Python environment.
- [x] Validate cache mode under the active ComfyUI Python environment.
- [x] Validate `symmetry_y` end-to-end under ComfyUI's active Python.
- [x] Validate `symmetry_z` end-to-end under ComfyUI's active Python.
- [x] Validate multi-axis symmetry combinations: `XY`, `XZ`, `YZ`, and `XYZ`.

## Remaining Audit / Hardening
- [ ] Audit Blender-backed preprocessing against addon edge cases like modifiers, shapekeys, and multi-object imports.
- [x] Add a high-poly guard in `QRemeshify OBJ` before invoking downstream QuadWild stages, with configurable face-count thresholds and clear user-facing errors/warnings.
- [ ] Add an optional high-poly decimation fallback in `QRemeshify Preprocess Mesh` that can reduce face count before `QRemeshify OBJ` runs.
- [ ] Add face/vertex count reporting to preprocessing/remesh metadata so guard decisions and decimation results are visible to users.

## Documentation
- [ ] Add a troubleshooting section for `bpy`, DLL loading, and backend failures.

## Refactoring
- [ ] Split `qremeshify_nodes/bpy_subprocess.py` into smaller modules: subprocess transport, BPY mesh worker utilities, non-BPY backend workers, and dispatch/registration.
- [ ] Remove duplicated BPY import/build/symmetry/OBJ export logic between `qremeshify_nodes/blender_backend.py` and `qremeshify_nodes/bpy_subprocess.py` by consolidating around one shared implementation.
- [ ] Break `preprocess_mesh_input(...)` in `qremeshify_nodes/preprocess_helpers.py` into smaller orchestration helpers for backend resolution, worker execution, sharp-backend resolution, metadata assembly, and output packaging.
- [ ] Extract backend-agnostic sharp-feature serialization so `LIBIGL` and `TRIMESH` worker paths stop duplicating edge-occurrence and convexity logic.
- [ ] Refactor `QRemeshifyOBJ.execute(...)` in `qremeshify_nodes/node_remesh.py` into smaller steps for input materialization, guard enforcement, sharp-input preparation, backend request creation, and output packaging.
- [ ] Split `qremeshify_nodes/backend.py` into native library loading, output-path derivation, and QuadWild parameter-building helpers.
- [ ] Split `qremeshify_nodes/artifacts.py` into data models, materialization helpers, and payload parsing helpers.
- [ ] Add shared schema/input builders for repeated node UI patterns like mesh-source selection and backend-selection inputs.

## Future Backlog
- [ ] Add progress-percentage reporting to all nodes that can expose meaningful runtime progress.
- [ ] Expose additional native methods from `third_party/quadwild` through the Python wrapper for better preprocessing, diagnostics, and future guard rails.
- [ ] Optional future: expose mirrored/full-mesh variants for intermediate outputs only if later debugging needs justify it. Current decision is to keep half-mesh intermediates authoritative.
- [ ] Optional future: add a dedicated debug/intermediate-output helper workflow or node if real debugging usage shows the current returned file paths are insufficient.
- [ ] Optional future: evaluate whether `.rosy` / trace-stage contracts should remain file-backed permanently or be abstracted behind internal temporary artifacts only.
- [ ] Add [NeuroCross](https://github.com/QiujieDong/NeurCross) as an additional quad mesh generation backend.
- [ ] Add a `setup.py`-driven build process for `third_party/quadwild`, and later extend that same cross-platform build path to NeuroCross.
