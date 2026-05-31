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
from .bpy_subprocess import run_qremeshify_backend_subprocess
from .constants import NODE_CATEGORY
from .errors import QRemeshifyError
from .load_3d_input import (
    list_input_3d_files,
    resolve_model_path_or_selected,
)
from .mesh_io import parse_float_list, prepare_output_workspace, prepare_workspace

DEFAULT_HIGH_POLY_FACE_LIMIT = 150000


def normalize_selected_input_obj(input_obj) -> str:
    """Normalize uploaded/selectable OBJ input to a resolved string path."""
    if input_obj and input_obj != "none":
        selected_path = resolve_model_path_or_selected(input_obj)
        return str(selected_path) if selected_path is not None else ""
    return ""


def materialize_remesh_working_obj(
    resolved_input_obj: str,
    mesh_artifact: QRemeshifyMeshArtifact | None,
    *,
    output_dir: str,
) -> tuple[Path, Path]:
    """Materialize the working OBJ used by the native backend."""
    mesh_payload_available = mesh_artifact is not None and bool(
        mesh_artifact.vertices and mesh_artifact.faces
    )

    if mesh_payload_available:
        workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_")
        stem = mesh_artifact.label or "qremeshify_mesh"
        working_obj = workspace_dir / f"{stem}.obj"
        materialize_mesh_artifact(mesh_artifact, str(working_obj))
        return workspace_dir, working_obj

    if resolved_input_obj:
        return prepare_workspace(resolved_input_obj, output_dir)

    if mesh_artifact is not None:
        workspace_dir = prepare_output_workspace(output_dir, prefix="qremeshify_")
        stem = mesh_artifact.label or "qremeshify_mesh"
        working_obj = workspace_dir / f"{stem}.obj"
        materialize_mesh_artifact(mesh_artifact, str(working_obj))
        return workspace_dir, working_obj

    raise QRemeshifyError(
        "QRemeshify OBJ requires either input_obj or mesh_artifact"
    )


def enforce_high_poly_guard(
    working_obj: Path,
    *,
    high_poly_face_limit: int,
    ignore_high_poly_guard: bool,
) -> int:
    """Check the face-count guard before invoking the native backend."""
    _, input_faces = parse_obj_payload(str(working_obj))
    face_count = len(input_faces)
    if (
        int(high_poly_face_limit) > 0
        and face_count > int(high_poly_face_limit)
        and not ignore_high_poly_guard
    ):
        raise QRemeshifyError(
            "Input mesh exceeds the high-poly guard for QRemeshify OBJ "
            f"({face_count} faces > {int(high_poly_face_limit)} limit). "
            "Decimate the mesh first with QRemeshify Preprocess Mesh, or set "
            "ignore_high_poly_guard=true to continue at your own risk."
        )
    return face_count


def derive_remesh_output_paths(working_obj: Path) -> tuple[Path, Path, Path, Path]:
    """Derive the remesh intermediate and final output paths."""
    mesh_prefix = str(working_obj.with_suffix(""))
    return (
        Path(f"{mesh_prefix}_rem.obj"),
        Path(f"{mesh_prefix}_rem_p0.obj"),
        Path(f"{mesh_prefix}_rem_p0_0_quadrangulation.obj"),
        Path(f"{mesh_prefix}_rem_p0_0_quadrangulation_smooth.obj"),
    )


def prepare_remesh_sharp_input(
    *,
    resolved_sharp_path: str,
    sharp_artifact: QRemeshifySharpArtifact | None,
    workspace_dir: Path,
    working_obj: Path,
    use_cache: bool,
    traced_path: Path,
    output_dir: str,
) -> str:
    """Prepare the sharp-feature input path and cache preconditions."""
    sharp_payload_available = sharp_artifact is not None and bool(
        sharp_artifact.feature_rows
    )
    sharp_path = "" if sharp_payload_available else resolved_sharp_path.strip()
    if sharp_path and not Path(sharp_path).expanduser().resolve().exists():
        raise FileNotFoundError(Path(sharp_path).expanduser().resolve())

    if use_cache and not output_dir.strip():
        raise QRemeshifyError(
            "use_cache=True requires a persistent output_dir so cached intermediates can be reused"
        )
    if use_cache:
        if not traced_path.exists():
            raise QRemeshifyError(
                f"use_cache=True requires an existing traced mesh at {traced_path}. "
                "Run once with use_cache=False in the same output_dir first."
            )
        return sharp_path

    if sharp_payload_available:
        return materialize_sharp_artifact(
            sharp_artifact,
            str(workspace_dir / f"{working_obj.stem}_artifact.sharp"),
        )
    if sharp_path:
        return str(Path(sharp_path).expanduser().resolve())
    return ""


def run_remesh_backend(
    *,
    working_obj: Path,
    use_cache: bool,
    sharp_path: str,
    sharp_angle: float,
    smooth: bool,
    scale_factor: float,
    fixed_chart_clusters: int,
    alpha: float,
    ilp_method: str,
    time_limit: int,
    gap_limit: float,
    minimum_gap: float,
    isometry: bool,
    regularity_quadrilaterals: bool,
    regularity_non_quadrilaterals: bool,
    regularity_non_quadrilaterals_weight: float,
    align_singularities: bool,
    align_singularities_weight: float,
    repeat_losing_constraints_iterations: bool,
    repeat_losing_constraints_quads: bool,
    repeat_losing_constraints_non_quads: bool,
    repeat_losing_constraints_align: bool,
    hard_parity_constraint: bool,
    flow_config: str,
    satsuma_config: str,
    time_limits: list[float],
    gap_limits: list[float],
) -> dict:
    """Run the isolated native backend subprocess."""
    return run_qremeshify_backend_subprocess(
        mesh_path=working_obj,
        remesh=not use_cache,
        sharp_features_path=sharp_path,
        sharp_angle=sharp_angle,
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


def build_remesh_outputs(
    *,
    result: dict,
    workspace_dir: Path,
    working_obj: Path,
    face_count: int,
    high_poly_face_limit: int,
    ignore_high_poly_guard: bool,
) -> IO.NodeOutput:
    """Build final node outputs and artifacts from native backend results."""
    remeshed_path = Path(result["remeshed_path"])
    traced_path = Path(result["traced_path"])
    final_path = Path(result["final_path"])

    final_vertices, final_faces = parse_obj_payload(str(final_path))
    remeshed_vertices, remeshed_faces = parse_obj_payload(str(remeshed_path))
    traced_vertices, traced_faces = parse_obj_payload(str(traced_path))
    output_mesh_artifact = build_mesh_artifact(
        obj_path=str(final_path),
        vertices=final_vertices,
        faces=final_faces,
        workspace_dir=str(workspace_dir),
        source_path=str(working_obj),
        backend="QREMESHIFY",
        label=Path(final_path).stem,
        metadata={
            "stage": "final",
            "input_face_count": str(face_count),
            "high_poly_face_limit": str(int(high_poly_face_limit)),
            "ignore_high_poly_guard": str(bool(ignore_high_poly_guard)).lower(),
        },
    )
    remeshed_mesh_artifact = build_mesh_artifact(
        obj_path=str(remeshed_path),
        vertices=remeshed_vertices,
        faces=remeshed_faces,
        workspace_dir=str(workspace_dir),
        source_path=str(working_obj),
        backend="QREMESHIFY",
        label=remeshed_path.stem,
        metadata={"stage": "remeshed"},
    )
    traced_mesh_artifact = build_mesh_artifact(
        obj_path=str(traced_path),
        vertices=traced_vertices,
        faces=traced_faces,
        workspace_dir=str(workspace_dir),
        source_path=str(working_obj),
        backend="QREMESHIFY",
        label=traced_path.stem,
        metadata={"stage": "traced"},
    )
    model_3d = Types.File3D(str(final_path))
    return IO.NodeOutput(
        str(final_path),
        str(workspace_dir),
        str(remeshed_path),
        str(traced_path),
        model_3d,
        output_mesh_artifact,
        remeshed_mesh_artifact,
        traced_mesh_artifact,
    )


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
            "This node includes a high-poly guard that can be overridden at the user's risk. "
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
                IO.Int.Input(
                    "high_poly_face_limit",
                    default=DEFAULT_HIGH_POLY_FACE_LIMIT,
                    min=0,
                    max=50000000,
                    step=1,
                    tooltip="Face-count guard for remeshing. If the input mesh exceeds this many faces, remeshing stops and suggests decimation in QRemeshify Preprocess Mesh. Set to 0 to disable the threshold.",
                ),
                IO.Boolean.Input(
                    "ignore_high_poly_guard",
                    default=False,
                    tooltip="Ignore the high-poly face-count guard and continue remeshing at your own risk.",
                ),
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
        high_poly_face_limit=DEFAULT_HIGH_POLY_FACE_LIMIT,
        ignore_high_poly_guard=False,
        use_cache=False,
        sharp_features_path="",
        callback_time_limit="3,5,10,20,30,60,90,120",
        callback_gap_limit="0.005,0.02,0.05,0.10,0.15,0.20,0.25,0.30",
        output_dir="",
        **kwargs,
    ) -> IO.NodeOutput:
        input_obj = normalize_selected_input_obj(input_obj)
        resolved_input_obj = resolve_mesh_input(input_obj, mesh_artifact)
        resolved_sharp_path = resolve_sharp_input(sharp_features_path, sharp_artifact)
        time_limits = parse_float_list(callback_time_limit, 8, "callback_time_limit")
        gap_limits = parse_float_list(callback_gap_limit, 8, "callback_gap_limit")

        workspace_dir, working_obj = materialize_remesh_working_obj(
            resolved_input_obj,
            mesh_artifact,
            output_dir=output_dir,
        )
        face_count = enforce_high_poly_guard(
            working_obj,
            high_poly_face_limit=int(high_poly_face_limit),
            ignore_high_poly_guard=bool(ignore_high_poly_guard),
        )
        _, traced_path, _, _ = derive_remesh_output_paths(working_obj)
        sharp_path = prepare_remesh_sharp_input(
            resolved_sharp_path=resolved_sharp_path,
            sharp_artifact=sharp_artifact,
            workspace_dir=workspace_dir,
            working_obj=working_obj,
            use_cache=use_cache,
            traced_path=traced_path,
            output_dir=output_dir,
        )
        result = run_remesh_backend(
            working_obj=working_obj,
            use_cache=use_cache,
            sharp_path=sharp_path,
            sharp_angle=sharp_angle,
            smooth=smooth,
            scale_factor=scale_factor,
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
            time_limits=time_limits,
            gap_limits=gap_limits,
        )
        return build_remesh_outputs(
            result=result,
            workspace_dir=workspace_dir,
            working_obj=working_obj,
            face_count=face_count,
            high_poly_face_limit=int(high_poly_face_limit),
            ignore_high_poly_guard=bool(ignore_high_poly_guard),
        )
