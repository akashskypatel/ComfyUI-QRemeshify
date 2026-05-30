"""Main QRemeshify remesh node."""

from pathlib import Path

from comfy_api.latest import IO, Types

from .artifacts import (
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
from .constants import NODE_CATEGORY
from .errors import QRemeshifyError
from .load_3d_input import (
    list_input_3d_files,
    resolve_model_path_or_selected,
)
from .mesh_io import parse_float_list, prepare_output_workspace, prepare_workspace


class QRemeshifyOBJ(IO.ComfyNode):
    """QRemeshify OBJ remesh node for ComfyUI."""

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyOBJ",
            display_name="QRemeshify OBJ",
            category=NODE_CATEGORY,
            description="Remesh an OBJ file using QRemeshify to create a high-quality quad mesh with optional smoothing and sharp feature preservation. "
            "The remeshed mesh is saved as an OBJ file and can be used for further processing. It is recommended to preprocess the mesh before remeshing. "
            "High polygon count meshes may take a long time to process or outright fail. Decimation is highly recommended for such meshes. "
            "If the remeshing fails, try reducing the target face count or simplifying the mesh first. "
            "Supplying sharp features is not required but can help preserve important details during remeshing.",
            inputs=[
                IO.Combo.Input(
                    "input_obj",
                    options=["none"] + sorted(list_input_3d_files({".obj"})),
                    upload=IO.UploadType.model,
                    tooltip="Select an OBJ file to remesh",
                ),
                IO.Boolean.Input("smooth", default=True, tooltip="Apply smoothing to the mesh"),
                IO.Float.Input(
                    "sharp_angle", default=35.0, min=0.0, max=180.0, step=0.1, tooltip="Sharp angle threshold for feature preservation (0.0-180.0)"
                ),
                IO.Float.Input(
                    "scale_factor", default=1.0, min=0.01, max=10.0, step=0.01, tooltip="Scale factor for the mesh (0.01-10.0)"
                ),
                IO.Int.Input(
                    "fixed_chart_clusters", default=0, min=0, max=100000, step=1, tooltip="Fixed chart clusters (0-100000)"
                ),
                IO.Float.Input("alpha", default=0.005, min=0.0, max=0.999, step=0.001, tooltip="Alpha parameter for remeshing (0.0-0.999)"),
                IO.Combo.Input(
                    "ilp_method",
                    options=["LEASTSQUARES", "ABS"],
                    default="LEASTSQUARES",
                    tooltip="ILP method for remeshing"
                ),
                IO.Int.Input("time_limit", default=200, min=1, max=86400, step=1, tooltip="Time limit for remeshing (1-86400)"),
                IO.Float.Input("gap_limit", default=0.0, min=0.0, max=1.0, step=0.001, tooltip="Gap limit for remeshing (0.0-1.0)"),
                IO.Float.Input(
                    "minimum_gap", default=0.4, min=0.0, max=1.0, step=0.001, tooltip="Minimum gap for remeshing (0.0-1.0)"
                ),
                IO.Boolean.Input("isometry", default=True, tooltip="Apply isometry to the mesh"),
                IO.Boolean.Input("regularity_quadrilaterals", default=True, tooltip="Apply regularity to quadrilaterals"),
                IO.Boolean.Input("regularity_non_quadrilaterals", default=True, tooltip="Apply regularity to non-quadrilaterals"),
                IO.Float.Input(
                    "regularity_non_quadrilaterals_weight",
                    default=0.9,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    tooltip="Weight for regularity of non-quadrilaterals"
                ),
                IO.Boolean.Input("align_singularities", default=True, tooltip="Align singularities"),
                IO.Float.Input(
                    "align_singularities_weight",
                    default=0.1,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    tooltip="Weight for aligning singularities"
                ),
                IO.Boolean.Input("repeat_losing_constraints_iterations", default=True, tooltip="Repeat losing constraints for iterations"),
                IO.Boolean.Input("repeat_losing_constraints_quads", default=False, tooltip="Repeat losing constraints for quads"),
                IO.Boolean.Input("repeat_losing_constraints_non_quads", default=False, tooltip="Repeat losing constraints for non-quads"),
                IO.Boolean.Input("repeat_losing_constraints_align", default=True, tooltip="Repeat losing constraints for alignment"),
                IO.Boolean.Input("hard_parity_constraint", default=True, tooltip="Apply hard parity constraint"),
                IO.Combo.Input(
                    "flow_config", options=["SIMPLE", "HALF"], default="SIMPLE", tooltip="Flow configuration"
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
                    tooltip="Satsuma configuration"
                ),
                IO.AnyType.Input("mesh_artifact", tooltip="In-memory mesh artifact"),
                IO.AnyType.Input("sharp_artifact", tooltip="In-memory sharp artifact"),
                IO.Boolean.Input("use_cache", default=False, tooltip="Use cache for remeshing"),
                IO.String.Input("sharp_features_path", default="", tooltip="Path to sharp features file"),
                IO.String.Input(
                    "callback_time_limit",
                    default="3,5,10,20,30,60,90,120",
                    tooltip="Callback time limits"
                ),
                IO.String.Input(
                    "callback_gap_limit",
                    default="0.005,0.02,0.05,0.10,0.15,0.20,0.25,0.30",
                    tooltip="Callback gap limits"
                ),
                IO.String.Input("output_dir", default="", tooltip="Output directory"),
            ],
            outputs=[
                IO.String.Output(display_name=   "output_obj", tooltip="Output OBJ file path"),
                IO.String.Output(display_name=   "workspace_dir", tooltip="Workspace directory path"),
                IO.String.Output(display_name=   "remeshed_obj", tooltip="Remeshed OBJ file path"),
                IO.String.Output(display_name=   "traced_obj", tooltip="Traced OBJ file path"),
                IO.File3DAny.Output(display_name="model_3d", tooltip="3D model file saved under '3d' directory"),
                IO.AnyType.Output(display_name=  "output_mesh_artifact", tooltip="Output in-memory mesh artifact"),
                IO.AnyType.Output(display_name=  "remeshed_mesh_artifact", tooltip="Remeshed in-memory mesh artifact"),
                IO.AnyType.Output(display_name=  "traced_mesh_artifact", tooltip="Traced in-memory mesh artifact"),
            ],
        )

    @classmethod
    def execute(
        cls,
        input_obj,
        smooth,
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
        callback_time_limit="3,5,10,20,30,60,90,120",
        callback_gap_limit="0.005,0.02,0.05,0.10,0.15,0.20,0.25,0.30",
        output_dir="",
        **kwargs,
    ) -> IO.NodeOutput:
        if input_obj and input_obj != "none":
            selected_path = resolve_model_path_or_selected(input_obj)
            input_obj = str(selected_path) if selected_path is not None else ""
        else:
            input_obj = ""

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

            backend.remesh_and_field(True, sharp_path, sharp_angle)
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
        model_3d = Types.File3D(str(final_path))
        return IO.NodeOutput(
            str(final_path),
            str(workspace_dir),
            str(backend.remeshed_path),
            str(backend.traced_path),
            model_3d,
            output_mesh_artifact,
            remeshed_mesh_artifact,
            traced_mesh_artifact,
        )
