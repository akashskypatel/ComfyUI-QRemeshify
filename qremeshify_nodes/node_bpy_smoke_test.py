"""Diagnostic ComfyUI node for probing Blender bpy availability."""

from comfy_api.latest import IO

from .bpy_subprocess import run_bpy_probe
from .constants import NODE_CATEGORY


class QRemeshifyBpySmokeTest(IO.ComfyNode):
    """Run progressively deeper bpy probes to isolate embedded Blender issues."""

    OUTPUT_NODE = True

    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="QRemeshifyBpySmokeTest",
            display_name="QRemeshify BPY Smoke Test",
            category=NODE_CATEGORY,
            description="Run progressively deeper bpy probes to isolate embedded Blender issues.",
            inputs=[
                IO.Combo.Input(
                    "probe_level",
                    options=["IMPORT_ONLY", "APP_INFO", "MESH_DATA", "BMESH"],
                    default="APP_INFO",
                    tooltip="Select the level of bpy probe to run",
                ),
            ],
            outputs=[
                IO.String.Output(display_name="probe_level", tooltip="Selected probe level"),
                IO.String.Output(display_name="status", tooltip="Probe status (ok/error)"),
                IO.String.Output(display_name="details", tooltip="Probe details/diagnostics"),
            ],
        )

    @classmethod
    def execute(cls, probe_level="APP_INFO", **kwargs) -> IO.NodeOutput:
        try:
            result = run_bpy_probe(probe_level)
            return IO.NodeOutput(
                result.get("probe_level", probe_level),
                "ok",
                result.get("details", ""),
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            return IO.NodeOutput(probe_level, "error", f"{type(exc).__name__}: {exc}")

    process = execute
