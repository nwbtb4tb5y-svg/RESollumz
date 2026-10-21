import logging
import queue
import shutil
import tempfile
import threading
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .client import CWBridgeCancelled, CWBridgeError, convert_file, find_bridge_command
from .xml_import import stage_xml_for_import


_logger = logging.getLogger("resollumz.cwbridge")
_SUPPORTED_FORMATS = {"ydr", "yft", "ydd", "ytd"}


class SOLLUMZ_OT_cwbridge_import_xml(Operator, ImportHelper):
    """Convert CodeWalker XML to a binary asset and import it into the current scene"""

    bl_idname = "sollumz.cwbridge_import_xml"
    bl_label = "Import CodeWalker XML to Scene"
    bl_options = {"UNDO"}

    filename_ext = ".xml"
    filter_glob: StringProperty(
        default="*.xml",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    filepath: StringProperty(subtype="FILE_PATH")
    resource_format: EnumProperty(
        name="Resource Format",
        items=(
            ("ydr", "YDR", "Drawable"),
            ("yft", "YFT", "Fragment"),
            ("ydd", "YDD", "Drawable dictionary"),
            ("ytd", "YTD", "Texture dictionary"),
        ),
        default="ydr",
    )
    gen9: BoolProperty(
        name="Gen9",
        description="Read XML using the GTA V Enhanced resource format",
        default=False,
    )

    def draw(self, _context):
        self.layout.prop(self, "resource_format")
        self.layout.prop(self, "gen9")

    def execute(self, context):
        xml_path = Path(bpy.path.abspath(self.filepath)).resolve()
        if not xml_path.is_file() or xml_path.suffix.casefold() != ".xml":
            self.report({"ERROR"}, "Select an existing CodeWalker XML file.")
            return {"CANCELLED"}

        suffix_format = xml_path.stem.rpartition(".")[2].casefold()
        format_name = suffix_format if suffix_format in _SUPPORTED_FORMATS else self.resource_format
        if format_name not in _SUPPORTED_FORMATS:
            self.report({"ERROR"}, "Supported XML resources are YDR, YFT, YDD, and YTD.")
            return {"CANCELLED"}

        from ..sollumz_preferences import get_addon_preferences

        preferences = get_addon_preferences(context)
        if not preferences.cwbridge_enabled:
            self.report({"ERROR"}, "Enable CWBridge Features in Sollumz preferences first.")
            return {"CANCELLED"}
        from .. import dependencies

        if not dependencies.IS_SZIO_NATIVE_AVAILABLE:
            message = dependencies.PYMATERIA_REQUIRED_MSG or "Binary resource formats require PyMateria."
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        try:
            bridge_command = find_bridge_command(preferences.cwbridge_executable)
        except CWBridgeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        executable_path = preferences.cwbridge_executable
        self._temp_directory = Path(tempfile.mkdtemp(prefix="resollumz-cwbridge-import-"))
        base_name = xml_path.stem
        if base_name.casefold().endswith(f".{format_name}"):
            base_name = base_name[:-(len(format_name) + 1)]
        self._binary_path = self._temp_directory / f"{base_name}.{format_name}"
        self._cancel_event = threading.Event()
        self._result_queue = queue.Queue()
        input_path = xml_path
        output_path = self._binary_path
        cancel_event = self._cancel_event
        result_queue = self._result_queue
        temp_directory = self._temp_directory
        gen9 = self.gen9

        def convert_xml():
            try:
                staged_xml_path = stage_xml_for_import(input_path, temp_directory, format_name)
                convert_file(
                    staged_xml_path,
                    output_path,
                    operation="from_xml",
                    gen9=gen9,
                    executable_path=executable_path,
                    bridge_command=bridge_command,
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                if cancel_event.is_set():
                    shutil.rmtree(temp_directory, ignore_errors=True)
                result_queue.put(exc)
            else:
                result_queue.put(output_path)

        self._worker = threading.Thread(target=convert_xml, name="RESollumzXmlImport", daemon=True)
        self._worker.start()
        context.window_manager.progress_begin(0, 1)
        self._progress_active = True
        if context.workspace is not None:
            context.workspace.status_text_set("Converting CodeWalker XML...")
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._cancel_event.set()
            self.report({"INFO"}, "Cancelling XML conversion...")
            return {"RUNNING_MODAL"}
        if event.type != "TIMER" or self._worker.is_alive():
            return {"PASS_THROUGH"}

        self._finish_progress(context)
        result = self._result_queue.get()
        if isinstance(result, Exception):
            self._remove_temp_directory()
            if isinstance(result, CWBridgeCancelled):
                self.report({"INFO"}, "XML conversion cancelled.")
                return {"CANCELLED"}
            _logger.error("Could not convert CodeWalker XML: %s", result)
            self.report({"ERROR"}, str(result))
            return {"CANCELLED"}

        self._binary_path = result
        try:
            import_result = bpy.ops.sollumz.import_assets(
                directory=str(self._binary_path.parent),
                files=[{"name": self._binary_path.name}],
            )
        except Exception as exc:
            self._remove_temp_directory()
            _logger.exception("Sollumz failed to import the converted asset")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self._remove_temp_directory()
        if import_result != {"FINISHED"}:
            self.report({"ERROR"}, "Sollumz could not import the converted asset.")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Imported {self._binary_path.name}.")
        return {"FINISHED"}

    def cancel(self, context):
        if hasattr(self, "_cancel_event"):
            self._cancel_event.set()
        if hasattr(self, "_timer") and self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._finish_progress(context)

    def _finish_progress(self, context):
        timer = getattr(self, "_timer", None)
        if timer is not None:
            context.window_manager.event_timer_remove(timer)
            self._timer = None
        if getattr(self, "_progress_active", False):
            context.window_manager.progress_end()
            self._progress_active = False
        if context.workspace is not None:
            context.workspace.status_text_set(None)

    def _remove_temp_directory(self):
        temp_directory = getattr(self, "_temp_directory", None)
        if temp_directory is not None and temp_directory.exists():
            shutil.rmtree(temp_directory)
