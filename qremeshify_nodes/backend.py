"""Native backend bindings for QRemeshify."""

from __future__ import annotations

import platform
from ctypes import POINTER, Structure, byref, c_bool, c_char_p, c_double, c_float, c_int, cdll
from pathlib import Path

from .constants import BACKEND_DIR, CONFIG_DIR, FLOW_CONFIG_FILES, ILP_METHODS, SATSUMA_CONFIG_FILES
from .errors import QRemeshifyError


class Parameters(Structure):
    _fields_ = [
        ("remesh", c_bool),
        ("sharpAngle", c_float),
        ("alpha", c_float),
        ("scaleFact", c_float),
        ("hasFeature", c_bool),
        ("hasField", c_bool),
    ]


class QRParameters(Structure):
    _fields_ = [
        ("useFlowSolver", c_bool),
        ("flow_config_filename", c_char_p),
        ("satsuma_config_filename", c_char_p),
        ("initialRemeshing", c_bool),
        ("initialRemeshingEdgeFactor", c_double),
        ("reproject", c_bool),
        ("splitConcaves", c_bool),
        ("finalSmoothing", c_bool),
        ("ilpMethod", c_int),
        ("alpha", c_double),
        ("isometry", c_bool),
        ("regularityQuadrilaterals", c_bool),
        ("regularityNonQuadrilaterals", c_bool),
        ("regularityNonQuadrilateralsWeight", c_double),
        ("alignSingularities", c_bool),
        ("alignSingularitiesWeight", c_double),
        ("repeatLosingConstraintsIterations", c_bool),
        ("repeatLosingConstraintsQuads", c_bool),
        ("repeatLosingConstraintsNonQuads", c_bool),
        ("repeatLosingConstraintsAlign", c_bool),
        ("feasibilityFix", c_bool),
        ("hardParityConstraint", c_bool),
        ("timeLimit", c_double),
        ("gapLimit", c_double),
        ("minimumGap", c_double),
        ("callbackTimeLimit", POINTER(c_float)),
        ("callbackGapLimit", POINTER(c_float)),
        ("chartSmoothingIterations", c_int),
        ("quadrangulationFixedSmoothingIterations", c_int),
        ("quadrangulationNonFixedSmoothingIterations", c_int),
        ("doubletRemoval", c_bool),
        ("resultSmoothingIterations", c_int),
        ("resultSmoothingNRing", c_double),
        ("resultSmoothingLaplacianIterations", c_int),
        ("resultSmoothingLaplacianNRing", c_double),
    ]


def default_qr_parameters() -> QRParameters:
    callback_time_limit = [3.0, 5.0, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0]
    callback_gap_limit = [0.005, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    params = QRParameters()
    params.initialRemeshing = True
    params.initialRemeshingEdgeFactor = 1
    params.reproject = True
    params.splitConcaves = False
    params.finalSmoothing = True
    params.doubletRemoval = True
    params.resultSmoothingIterations = 5
    params.resultSmoothingNRing = 3
    params.resultSmoothingLaplacianIterations = 2
    params.resultSmoothingLaplacianNRing = 3

    params.alpha = 0.005
    params.ilpMethod = 1
    params.timeLimit = 200
    params.gapLimit = 0.0
    params.callbackTimeLimit = (c_float * len(callback_time_limit))(*callback_time_limit)
    params.callbackGapLimit = (c_float * len(callback_gap_limit))(*callback_gap_limit)
    params.minimumGap = 0.4
    params.isometry = True
    params.regularityQuadrilaterals = True
    params.regularityNonQuadrilaterals = True
    params.regularityNonQuadrilateralsWeight = 0.9
    params.alignSingularities = True
    params.alignSingularitiesWeight = 0.1
    params.repeatLosingConstraintsIterations = True
    params.repeatLosingConstraintsQuads = False
    params.repeatLosingConstraintsNonQuads = False
    params.repeatLosingConstraintsAlign = True
    params.hardParityConstraint = True
    params.useFlowSolver = True
    params.chartSmoothingIterations = 0
    params.quadrangulationFixedSmoothingIterations = 0
    params.quadrangulationNonFixedSmoothingIterations = 0
    params.feasibilityFix = False
    return params


class QuadwildBackend:
    def __init__(self, mesh_path: Path) -> None:
        if not mesh_path:
            raise QRemeshifyError("mesh_path is empty")
        if not BACKEND_DIR.exists():
            raise QRemeshifyError(f"Backend directory not found: {BACKEND_DIR}")
        if not CONFIG_DIR.exists():
            raise QRemeshifyError(f"Config directory not found: {CONFIG_DIR}")

        system = platform.system()
        if system == "Windows":
            quadwild_name = "lib_quadwild.dll"
            quadpatches_name = "lib_quadpatches.dll"
        elif system == "Darwin":
            quadwild_name = "liblib_quadwild.dylib"
            quadpatches_name = "liblib_quadpatches.dylib"
        else:
            quadwild_name = "liblib_quadwild.so"
            quadpatches_name = "liblib_quadpatches.so"

        quadwild_path = BACKEND_DIR / quadwild_name
        quadpatches_path = BACKEND_DIR / quadpatches_name
        if not quadwild_path.exists():
            raise QRemeshifyError(f"QuadWild library not found: {quadwild_path}")
        if not quadpatches_path.exists():
            raise QRemeshifyError(f"QuadPatches library not found: {quadpatches_path}")

        self.quadwild = cdll.LoadLibrary(str(quadwild_path))
        self.quadpatches = cdll.LoadLibrary(str(quadpatches_path))

        self.quadwild.remeshAndField2.argtypes = [POINTER(Parameters), c_char_p, c_char_p, c_char_p]
        self.quadwild.remeshAndField2.restype = None
        self.quadwild.trace2.argtypes = [c_char_p]
        self.quadwild.trace2.restype = c_bool
        self.quadpatches.quadPatches.argtypes = [c_char_p, POINTER(QRParameters), c_float, c_int, c_bool]
        self.quadpatches.quadPatches.restype = c_int

        self.mesh_path = mesh_path
        mesh_prefix = str(mesh_path.with_suffix(""))
        self.sharp_path = Path(f"{mesh_prefix}_rem.sharp")
        self.field_path = Path(f"{mesh_prefix}_rem.rosy")
        self.remeshed_path = Path(f"{mesh_prefix}_rem.obj")
        self.traced_path = Path(f"{mesh_prefix}_rem_p0.obj")
        self.output_path = Path(f"{mesh_prefix}_rem_p0_0_quadrangulation.obj")
        self.output_smoothed_path = Path(f"{mesh_prefix}_rem_p0_0_quadrangulation_smooth.obj")

    def remesh_and_field(self, remesh: bool, sharp_features_path: str, sharp_angle: float) -> None:
        sharp_path = sharp_features_path if sharp_features_path else str(self.sharp_path)
        params = Parameters(
            remesh=remesh,
            sharpAngle=sharp_angle if sharp_features_path else -1,
            hasFeature=bool(sharp_features_path),
            hasField=False,
            alpha=0.01,
            scaleFact=1,
        )
        try:
            self.quadwild.remeshAndField2(
                byref(params),
                str(self.mesh_path).encode("utf-8"),
                sharp_path.encode("utf-8"),
                str(self.field_path).encode("utf-8"),
            )
        except Exception as exc:  # pragma: no cover
            raise QRemeshifyError("remeshAndField failed") from exc

        if not self.remeshed_path.exists():
            raise QRemeshifyError(f"Expected remeshed output was not created: {self.remeshed_path}")

    def trace(self) -> None:
        try:
            success = self.quadwild.trace2(str(self.remeshed_path.with_suffix("")).encode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise QRemeshifyError("trace failed") from exc
        if not success or not self.traced_path.exists():
            raise QRemeshifyError(f"Expected traced output was not created: {self.traced_path}")

    def quadrangulate(
        self,
        enable_smoothing: bool,
        scale_fact: float,
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
        callback_time_limit: list[float],
        callback_gap_limit: list[float],
    ) -> None:
        params = default_qr_parameters()
        params.alpha = alpha
        params.ilpMethod = ILP_METHODS[ilp_method]
        params.timeLimit = time_limit
        params.gapLimit = gap_limit
        params.minimumGap = minimum_gap
        params.isometry = isometry
        params.regularityQuadrilaterals = regularity_quadrilaterals
        params.regularityNonQuadrilaterals = regularity_non_quadrilaterals
        params.regularityNonQuadrilateralsWeight = regularity_non_quadrilaterals_weight
        params.alignSingularities = align_singularities
        params.alignSingularitiesWeight = align_singularities_weight
        params.repeatLosingConstraintsIterations = repeat_losing_constraints_iterations
        params.repeatLosingConstraintsQuads = repeat_losing_constraints_quads
        params.repeatLosingConstraintsNonQuads = repeat_losing_constraints_non_quads
        params.repeatLosingConstraintsAlign = repeat_losing_constraints_align
        params.hardParityConstraint = hard_parity_constraint
        params.flow_config_filename = str(CONFIG_DIR / FLOW_CONFIG_FILES[flow_config]).encode("utf-8")
        params.satsuma_config_filename = str(CONFIG_DIR / SATSUMA_CONFIG_FILES[satsuma_config]).encode("utf-8")
        params.callbackTimeLimit = (c_float * len(callback_time_limit))(*callback_time_limit)
        params.callbackGapLimit = (c_float * len(callback_gap_limit))(*callback_gap_limit)

        try:
            self.quadpatches.quadPatches(
                str(self.traced_path).encode("utf-8"),
                byref(params),
                scale_fact,
                fixed_chart_clusters,
                enable_smoothing,
            )
        except Exception as exc:  # pragma: no cover
            raise QRemeshifyError("quadPatches failed") from exc

        final_path = self.output_smoothed_path if enable_smoothing else self.output_path
        if not final_path.exists():
            raise QRemeshifyError(f"Expected quadrangulated output was not created: {final_path}")
