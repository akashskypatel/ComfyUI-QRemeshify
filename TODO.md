# TODO

## Completed Migration Work
- [x] Add `bpy` as an optional high-fidelity preprocessing backend.
- [x] Implement first-pass symmetry preprocessing/postprocessing on the `bpy` path.
- [x] Implement cache mode in `QRemeshify OBJ` using previously generated intermediate files.
- [x] Fix the OBJ/MTL warning seen during symmetry postprocess import.
- [x] Add native in-memory ComfyUI mesh/sharp artifact datatypes so nodes can pass richer geometry objects instead of only bare path strings.
- [x] Remove the remaining non-runtime `QRemeshify` reference artifacts.

## Testing And Validation
- [x] Validate the `bpy` path end-to-end inside ComfyUI's active Python environment.
- [x] Validate cache mode under the active ComfyUI Python environment.
- [x] Validate `symmetry_y` end-to-end under ComfyUI's active Python.
- [x] Validate `symmetry_z` end-to-end under ComfyUI's active Python.
- [x] Validate multi-axis symmetry combinations: `XY`, `XZ`, `YZ`, and `XYZ`.

## Remaining Audit / Hardening
- [ ] Audit Blender-backed preprocessing against addon edge cases like modifiers, shapekeys, and multi-object imports.

## Documentation
- [ ] Add a troubleshooting section for `bpy`, DLL loading, and backend failures.

## Future Backlog
- [ ] Optional future: expose mirrored/full-mesh variants for intermediate outputs only if later debugging needs justify it. Current decision is to keep half-mesh intermediates authoritative.
- [ ] Optional future: add a dedicated debug/intermediate-output helper workflow or node if real debugging usage shows the current returned file paths are insufficient.
- [ ] Add [NeuroCross](https://github.com/QiujieDong/NeurCross) as an additional quad mesh generation backend.
- [ ] Add a `setup.py`-driven build process for `third_party/quadwild`, and later extend that same cross-platform build path to NeuroCross.
