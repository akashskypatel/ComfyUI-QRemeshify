"""Main QRemeshify remesh node."""

from pathlib import Path

from comfy_api.latest import IO

from .artifacts import (
    MESH_ARTIFACT_TYPE,
    SHARP_ARTIFACT_TYPE,
    QRemeshifyMeshArtifact,
    QRemeshifySharpArtifact,
    build_mesh_artifact,
    materialize_mesh_artifact,
    materialize_sharp_artifact,
    parse_obj_payload,
    resolve_mesh_input,
    resolve_sharp_input,
)
from .backend import QuadwildBackend
from .blender_backend import (
    bpy_available,
    postprocess_obj_with_symmetry_with_bpy,
    preprocess_obj_with_symmetry_with_bpy,
)
from .constants import NODE_CATEGORY
from .errors import QRemeshifyError
from .mesh_io import parse_float_list, prepare_output_workspace, prepare_workspace
from .sharp_features import generate_sharp_features


class QRemeshifyOBJ(IO.ComfyNode):
    """QRemeshify OBJ remesh node for ComfyUI."""

    CATEGORY = NODE_CATEGORY

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyOBJ",
            display_name="QRemeshify OBJ",
            category=cls.CATEGORY,
            inputs=[
                IO.String.Input("input_obj", default=""),
                IO.Boolean.Input("preprocess", default=True),
                IO.Boolean.Input("smooth", default=True),
                IO.Boolean.Input("detect_sharp", default=False),
                IO.Float.Input(
                    "sharp_angle", default=35.0, min=0.0, max=180.0, step=0.1
                ),
                IO.Float.Input(
                    "scale_factor", default=1.0, min=0.01, max=10.0, step=0.01
                ),
                IO.Int.Input(
                    "fixed_chart_clusters", default=0, min=0, max=100000, step=1
                ),
                IO.Float.Input("alpha", default=0.005, min=0.0, max=0.999, step=0.001),
                IO.Combo.Input(
                    "ilp_method",
                    options=["LEASTSQUARES", "ABS"],
                    default="LEASTSQUARES",
                ),
                IO.Int.Input("time_limit", default=200, min=1, max=86400, step=1),
                IO.Float.Input("gap_limit", default=0.0, min=0.0, max=1.0, step=0.001),
                IO.Float.Input(
                    "minimum_gap", default=0.4, min=0.0, max=1.0, step=0.001
                ),
                IO.Boolean.Input("isometry", default=True),
                IO.Boolean.Input("regularity_quadrilaterals", default=True),
                IO.Boolean.Input("regularity_non_quadrilaterals", default=True),
                IO.Float.Input(
                    "regularity_non_quadrilaterals_weight",
                    default=0.9,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                ),
                IO.Boolean.Input("align_singularities", default=True),
                IO.Float.Input(
                    "align_singularities_weight",
                    default=0.1,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                ),
                IO.Boolean.Input("repeat_losing_constraints_iterations", default=True),
                IO.Boolean.Input("repeat_losing_constraints_quads", default=False),
                IO.Boolean.Input("repeat_losing_constraints_non_quads", default=False),
                IO.Boolean.Input("repeat_losing_constraints_align", default=True),
                IO.Boolean.Input("hard_parity_constraint", default=True),
                IO.Combo.Input(
                    "flow_config", options=["SIMPLE", "HALF"], default="SIMPLE"
                ),
                IO.Combo.Input(
                    "satsuma_config",
                    options=[
                        "DEFAULT",
                        "MST",
                        "ROUND2EVEN",
                        "SYMMDC",
                        "EDGETHRU",
                        "LEMON",
                        "NODETHRU",
                    ],
                    default="DEFAULT",
                ),
                IO.CustomInput(MESH_ARTIFACT_TYPE, "mesh_artifact"),
                IO.CustomInput(SHARP_ARTIFACT_TYPE, "sharp_artifact"),
                IO.Boolean.Input("use_cache", default=False),
                IO.String.Input("sharp_features_path", default="", is_list=False),
                IO.Combo.Input(
                    "sharp_backend",
                    options=["AUTO", "BPY", "LIBIGL", "TRIMESH"],
                    default="AUTO",
                ),
                IO.String.Input(
                    "callback_time_limit",
                    default="3,5,10,20,30,60,90,120",
                    is_list=False,
                ),
                IO.String.Input(
                    "callback_gap_limit",
                    default="0.005,0.02,0.05,0.10,0.15,0.20,0.25,0.30",
                    is_list=False,
                ),
                IO.String.Input("output_dir", default="", is_list=False),
                IO.Boolean.Input("symmetry_x", default=False),
                IO.Boolean.Input("symmetry_y", default=False),
                IO.Boolean.Input("symmetry_z", default=False),
            ],
            outputs=[
                IO.String.Output(display_name="output_obj"),
                IO.String.Output(display_name="workspace_dir"),
                IO.String.Output(display_name="remeshed_obj"),
                IO.String.Output(display_name="traced_obj"),
                IO.CustomOutput(
                    MESH_ARTIFACT_TYPE, display_name="output_mesh_artifact"
                ),
                IO.CustomOutput(
                    MESH_ARTIFACT_TYPE, display_name="remeshed_mesh_artifact"
                ),
                IO.CustomOutput(
                    MESH_ARTIFACT_TYPE, display_name="traced_mesh_artifact"
                ),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_obj,
        preprocess,
        smooth,
        detect_sharp,
        sharp_angle,
        scale_factor,
        fixed_chart_clusters,
        alpha,
        ilp_method,
        time_limit,
        gap_limit,
        minimum_gap,
        isometry,
        regularity_quadrilaterals,
        regularity_non_quadrilaterals,
        regularity_non_quadrilaterals_weight,
        align_singularities,
        align_singularities_weight,
        repeat_losing_constraints_iterations,
        repeat_losing_constraints_quads,
        repeat_losing_constraints_non_quads,
        repeat_losing_constraints_align,
        hard_parity_constraint,
        flow_config,
        satsuma_config,
        mesh_artifact: QRemeshifyMeshArtifact | None = None,
        sharp_artifact: QRemeshifySharpArtifact | None = None,
        use_cache=False,
        sharp_features_path="",
        sharp_backend="AUTO",
        callback_time_limit="3,5,10,20,30,60,90,120",
        callback_gap_limit="0.005,0.02,0.05,0.10,0.15,0.20,0.25,0.30",
        output_dir="",
        symmetry_x=False,
        symmetry_y=False,
        symmetry_z=False,
        **kwargs,
    ) -> IO.NodeOutput:
        resolved_input_obj = resolve_mesh_input(input_obj, mesh_artifact)
        resolved_sharp_path = resolve_sharp_input(sharp_features_path, sharp_artifact)
        time_limits = parse_float_list(callback_time_limit, 8, "callback_time_limit")
        gap_limits = parse_float_list(callback_gap_limit, 8, "callback_gap_limit")

        mesh_payload_available = mesh_artifact is not None and bool(
            mesh_artifact.vertices and mesh_artifact.faces
        )
        sharp_payload_available = sharp_artifact is not None and bool(
            sharp_artifact.feature_rows
        )

        if mesh_payload_available:
            workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_")
            stem = mesh_artifact.label or "qremeshify_mesh"
            working_obj = workspace_dir / f"{stem}.obj"
            materialize_mesh_artifact(mesh_artifact, str(working_obj))
        elif resolved_input_obj:
            workspace_dir, working_obj = prepare_workspace(
                resolved_input_obj, output_dir
            )
        elif mesh_artifact is not None:
            workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_")
            stem = mesh_artifact.label or "qremeshify_mesh"
            working_obj = workspace_dir / f"{stem}.obj"
            materialize_mesh_artifact(mesh_artifact, str(working_obj))
        else:
            raise QRemeshifyError(
                "QRemeshify OBJ requires either input_obj or mesh_artifact"
            )

        backend = QuadwildBackend(working_obj)

        if use_cache and not output_dir.strip():
            raise QRemeshifyError(
                "use_cache=True requires a persistent output_dir so cached intermediates can be reused"
            )

        if symmetry_x or symmetry_y or symmetry_z:
            if not bpy_available():
                raise QRemeshifyError(
                    "Symmetry currently requires Blender's Python module 'bpy' to be available in the same environment as ComfyUI"
                )
            if not use_cache:
                preprocess_obj_with_symmetry_with_bpy(
                    working_obj,
                    working_obj,
                    symmetry_x,
                    symmetry_y,
                    symmetry_z,
                )
        sharp_path = "" if sharp_payload_available else resolved_sharp_path.strip()
        if sharp_path and not Path(sharp_path).expanduser().resolve().exists():
            raise FileNotFoundError(Path(sharp_path).expanduser().resolve())

        if use_cache:
            if not backend.traced_path.exists():
                raise QRemeshifyError(
                    f"use_cache=True requires an existing traced mesh at {backend.traced_path}. "
                    "Run once with use_cache=False in the same output_dir first."
                )
        else:
            if sharp_payload_available:
                sharp_path = materialize_sharp_artifact(
                    sharp_artifact,
                    str(workspace_dir / f"{working_obj.stem}_artifact.sharp"),
                )
            elif sharp_path:
                sharp_path = str(Path(sharp_path).expanduser().resolve())
            elif detect_sharp:
                resolved_backend = sharp_backend
                if sharp_backend == "AUTO":
                    resolved_backend = "BPY" if bpy_available() else "LIBIGL"
                sharp_path = str(
                    generate_sharp_features(
                        working_obj,
                        working_obj,
                        sharp_angle,
                        workspace_dir / f"{working_obj.stem}_generated.sharp",
                        resolved_backend,
                    )
                )

            backend.remesh_and_field(preprocess, sharp_path, sharp_angle)
            backend.trace()

        backend.quadrangulate(
            enable_smoothing=smooth,
            scale_fact=scale_factor,
            fixed_chart_clusters=fixed_chart_clusters,
            alpha=alpha,
            ilp_method=ilp_method,
            time_limit=time_limit,
            gap_limit=gap_limit,
            minimum_gap=minimum_gap,
            isometry=isometry,
            regularity_quadrilaterals=regularity_quadrilaterals,
            regularity_non_quadrilaterals=regularity_non_quadrilaterals,
            regularity_non_quadrilaterals_weight=regularity_non_quadrilaterals_weight,
            align_singularities=align_singularities,
            align_singularities_weight=align_singularities_weight,
            repeat_losing_constraints_iterations=repeat_losing_constraints_iterations,
            repeat_losing_constraints_quads=repeat_losing_constraints_quads,
            repeat_losing_constraints_non_quads=repeat_losing_constraints_non_quads,
            repeat_losing_constraints_align=repeat_losing_constraints_align,
            hard_parity_constraint=hard_parity_constraint,
            flow_config=flow_config,
            satsuma_config=satsuma_config,
            callback_time_limit=time_limits,
            callback_gap_limit=gap_limits,
        )

        final_path = backend.output_smoothed_path if smooth else backend.output_path
        if symmetry_x or symmetry_y or symmetry_z:
            mirrored_final_path = (
                workspace_dir / f"{Path(final_path).stem}_symmetry.obj"
            )
            final_path = postprocess_obj_with_symmetry_with_bpy(
                Path(final_path),
                mirrored_final_path,
                symmetry_x,
                symmetry_y,
                symmetry_z,
            )
        final_vertices, final_faces = parse_obj_payload(str(final_path))
        remeshed_vertices, remeshed_faces = parse_obj_payload(
            str(backend.remeshed_path)
        )
        traced_vertices, traced_faces = parse_obj_payload(str(backend.traced_path))
        output_mesh_artifact = build_mesh_artifact(
            obj_path=str(final_path),
            vertices=final_vertices,
            faces=final_faces,
            workspace_dir=str(workspace_dir),
            source_path=str(working_obj),
            backend="QREMESHIFY",
            label=Path(final_path).stem,
            metadata={"stage": "final"},
        )
        remeshed_mesh_artifact = build_mesh_artifact(
            obj_path=str(backend.remeshed_path),
            vertices=remeshed_vertices,
            faces=remeshed_faces,
            workspace_dir=str(workspace_dir),
            source_path=str(working_obj),
            backend="QREMESHIFY",
            label=backend.remeshed_path.stem,
            metadata={"stage": "remeshed"},
        )
        traced_mesh_artifact = build_mesh_artifact(
            obj_path=str(backend.traced_path),
            vertices=traced_vertices,
            faces=traced_faces,
            workspace_dir=str(workspace_dir),
            source_path=str(working_obj),
            backend="QREMESHIFY",
            label=backend.traced_path.stem,
            metadata={"stage": "traced"},
        )
        return IO.NodeOutput(
            str(final_path),
            str(workspace_dir),
            str(backend.remeshed_path),
            str(backend.traced_path),
            output_mesh_artifact,
            remeshed_mesh_artifact,
            traced_mesh_artifact,
        )
