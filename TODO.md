# TODO

- [x] Add `bpy` as an optional high-fidelity preprocessing backend.
- [x] Validate the `bpy` path end-to-end inside ComfyUI's active Python environment.
- [x] Implement first-pass symmetry preprocessing/postprocessing on the `bpy` path.
- [x] Implement cache mode in `QRemeshify OBJ` using previously generated intermediate files.
- [x] Validate cache mode under the active ComfyUI Python environment.
- [x] Fix the OBJ/MTL warning seen during symmetry postprocess import.
- [ ] Validate `symmetry_y` end-to-end under ComfyUI's active Python.
- [ ] Validate `symmetry_z` end-to-end under ComfyUI's active Python.
- [ ] Validate multi-axis symmetry combinations: `XY`, `XZ`, `YZ`, and `XYZ`.
- [ ] Decide whether mirrored/full-mesh variants should also be exposed for intermediate outputs.
- [ ] Add a dedicated debug/intermediate-output helper workflow or node.
- [ ] Audit Blender-backed preprocessing against addon edge cases like modifiers, shapekeys, and multi-object imports.
- [ ] Add a troubleshooting section for `bpy`, DLL loading, and backend failures.
- [ ] Decide whether to keep or remove the remaining non-runtime `QRemeshify` reference artifacts:
  - `QRemeshify/lib/config` duplicate copy
  - `QRemeshify/blender_manifest.toml`
