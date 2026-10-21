import os
import queue
import threading
from pathlib import Path

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    StringProperty,
)
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

from ... import logger
from ...cwbridge.client import CWBridgeCancelled, CWBridgeError, find_bridge_command
from ...cwbridge.ytd_index import YtdIndexResult, choose_texture, index_ytd_directory
from ...sollumz_operators import ExportAssetsOperatorImpl, ImportAssetsOperatorImpl
from ..properties import get_texture_name
from ..utils import (
    get_selected_txd,
    get_selected_txd_source,
)


class SOLLUMZ_OT_txd_create(Operator):
    """Add a texture dictionary to the project"""

    bl_idname = "sollumz.txd_create"
    bl_label = "Create Texture Dictionary"

    def execute(self, context):
        txds = context.scene.sz_txds

        existing_names = {t.name for t in txds.texture_dictionaries}
        name = "txd"
        if name in existing_names:
            n = 1
            while (name := f"txd_{n:02d}") in existing_names:
                n += 1

        txd = txds.new_texture_dictionary()
        txd.name = name
        return {"FINISHED"}


class SOLLUMZ_OT_txd_delete(Operator):
    """Delete the selected texture dictionary from the project"""

    bl_idname = "sollumz.txd_delete"
    bl_label = "Delete Texture Dictionary"

    @classmethod
    def poll(cls, context):
        return len(context.scene.sz_txds.texture_dictionaries) > 0

    def execute(self, context):
        context.scene.sz_txds.texture_dictionaries.remove_selected()
        return {"FINISHED"}


class SOLLUMZ_OT_txd_create_texture(Operator):
    """Add a texture slot to the texture dictionary"""

    bl_idname = "sollumz.txd_create_texture"
    bl_label = "Create Texture"

    @classmethod
    def poll(cls, context):
        return get_selected_txd(context) is not None

    def execute(self, context):
        txd = get_selected_txd(context)
        if txd is None:
            return {"CANCELLED"}

        txd.new_texture()
        return {"FINISHED"}


class SOLLUMZ_OT_txd_add_textures_from_dds(Operator, ImportHelper):
    """Add one or more DDS files as textures to the selected texture dictionary"""

    bl_idname = "sollumz.txd_add_textures_from_dds"
    bl_label = "Add Textures from DDS"

    filter_glob: StringProperty(default="*.dds", options={"HIDDEN"}, maxlen=255)

    files: CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return get_selected_txd(context) is not None

    def execute(self, context):
        txd = get_selected_txd(context)

        if not self.directory or len(self.files) == 0 or self.files[0].name == "":
            self.report({"ERROR"}, "No DDS file selected.")
            return {"CANCELLED"}

        directory = Path(bpy.path.abspath(self.directory))
        added = 0
        for f in sorted(self.files, key=lambda f: f.name):
            filepath = directory / f.name
            if not filepath.is_file():
                logger.warning(f"DDS file does not exist: {filepath}")
                continue

            img = bpy.data.images.load(str(filepath), check_existing=True)
            if not img.packed_file:
                img.pack()
            txd.new_texture(img)
            added += 1

        self.report({"INFO"}, f"Added {added} texture(s) to '{txd.name}'.")
        return {"FINISHED"}


class SOLLUMZ_OT_txd_delete_texture(Operator):
    """Delete the selected texture(s) from the texture dictionary"""

    bl_idname = "sollumz.txd_delete_texture"
    bl_label = "Delete Texture"

    @classmethod
    def poll(cls, context):
        txd = get_selected_txd(context)
        return txd is not None and len(txd.textures) > 0

    def execute(self, context):
        get_selected_txd(context).textures.remove_selected()
        return {"FINISHED"}


class SOLLUMZ_OT_txd_create_source(Operator):
    """Add a textures source to the texture dictionary"""

    bl_idname = "sollumz.txd_create_source"
    bl_label = "Create Source"

    @classmethod
    def poll(cls, context):
        return get_selected_txd(context) is not None

    def execute(self, context):
        txd = get_selected_txd(context)
        txd.new_source()
        return {"FINISHED"}


class SOLLUMZ_OT_txd_delete_source(Operator):
    """Delete the selected source(s) from the texture dictionary"""

    bl_idname = "sollumz.txd_delete_source"
    bl_label = "Delete Source"

    @classmethod
    def poll(cls, context):
        txd = get_selected_txd(context)
        return txd is not None and len(txd.sources) > 0

    def execute(self, context):
        get_selected_txd(context).sources.remove_selected()
        return {"FINISHED"}


class SOLLUMZ_OT_txd_source_use_all_images(Operator):
    """Delete the selected source(s) from the texture dictionary"""

    bl_idname = "sollumz.txd_source_use_all_images"
    bl_label = "Use All Images"

    use: BoolProperty(name="Use", default=True)

    @classmethod
    def poll(cls, context):
        src = get_selected_txd_source(context)
        return src is not None and len(src.images) > 0

    def execute(self, context):
        src = get_selected_txd_source(context)
        use = self.use
        for img in src.images:
            img.use = use
        return {"FINISHED"}


class SOLLUMZ_OT_txd_refresh_sources(Operator):
    """Refresh all sources in the texture dictionary"""

    bl_idname = "sollumz.txd_refresh_sources"
    bl_label = "Refresh Sources"

    @classmethod
    def poll(cls, context):
        return get_selected_txd(context) is not None

    def execute(self, context):
        txd = get_selected_txd(context)
        txd.refresh_from_sources(context)
        return {"FINISHED"}


class SOLLUMZ_OT_txd_find_missing(Operator):
    """Find images whose files are missing and replace them with matching textures from the available texture dictionaries"""

    bl_idname = "sollumz.txd_find_missing"
    bl_label = "Find Missing Textures using TXDs"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return any(len(txd.textures) > 0 for txd in context.scene.sz_txds.texture_dictionaries)

    def execute(self, context):
        txd_images = set()
        txd_images_by_name = {}
        for txd in context.scene.sz_txds.texture_dictionaries:
            for slot in txd.textures:
                if slot.image is not None:
                    if name := slot.name:
                        txd_images_by_name.setdefault(name, slot.image)
                    txd_images.add(slot.image)

        replaced = []
        for image in list(bpy.data.images):
            if image in txd_images or not self._has_missing_file(image):
                continue

            new_image = txd_images_by_name.get(get_texture_name(image))
            if new_image is None or new_image is image:
                continue

            try:
                image.user_remap(new_image)
            except Exception as e:
                logger.warning(f"Failed to update texture '{image.name}': {e}")
                continue

            replaced.append(image)

        # `batch_remove` requires the IDs to be fully unused. `user_remap` leaves them at zero users, but an
        # image kept around by a fake user must not be deleted.
        unused = [image for image in replaced if image.users == 0]
        if unused:
            bpy.data.batch_remove(unused)

        self.report({"INFO"}, f"Found {len(replaced)} missing texture(s).")
        return {"FINISHED"}

    def _has_missing_file(self, image: bpy.types.Image) -> bool:
        """An image whose source file is neither on disk nor packed."""
        return (
            not image.packed_files
            and image.source == "FILE"
            and not os.path.exists(bpy.path.abspath(image.filepath, library=image.library))
        )


class SOLLUMZ_OT_txd_find_in_ytd_folder(Operator):
    """Index YTD files and connect matching textures to selected models"""

    bl_idname = "sollumz.txd_find_in_ytd_folder"
    bl_label = "Find Textures in YTD Folder"
    bl_options = {"UNDO"}

    directory: StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})
    recursive: BoolProperty(
        name="Search Subfolders",
        description="Search the selected folder recursively",
        default=True,
    )
    use_shared_directories: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})
    force_reindex: BoolProperty(
        name="Reindex YTD Files",
        description="Re-extract YTD files instead of using valid cached results",
        default=False,
    )
    gen9: BoolProperty(
        name="Gen9",
        description="Read YTD dictionaries using the GTA V Enhanced resource format",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def invoke(self, context, event):
        if self.use_shared_directories:
            return context.window_manager.invoke_props_dialog(self, width=500)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "gen9")
        layout.prop(self, "force_reindex")
        if not self.use_shared_directories:
            layout.prop(self, "recursive")

    def execute(self, context):
        targets = _selected_missing_texture_samplers(context)
        if not targets:
            self.report({"WARNING"}, "Select a model with missing Sollumz texture samplers first.")
            return {"CANCELLED"}

        from ...sollumz_preferences import get_addon_preferences

        preferences = get_addon_preferences(context)
        if not preferences.cwbridge_enabled:
            self.report({"ERROR"}, "Enable CWBridge Features in Sollumz preferences first.")
            return {"CANCELLED"}

        if self.use_shared_directories:
            source_directories = []
            for shared_directory in preferences.shared_textures_directories:
                directory = Path(bpy.path.abspath(shared_directory.path))
                if not directory.is_dir():
                    logger.warning(f"Configured shared texture directory does not exist: {directory}")
                    continue
                source_directories.append((directory.resolve(), shared_directory.recursive))
        else:
            directory = Path(bpy.path.abspath(self.directory))
            if not directory.is_dir():
                self.report({"ERROR"}, "Select an existing folder containing YTD files.")
                return {"CANCELLED"}
            source_directories = [(directory.resolve(), self.recursive)]

        unique_directories = {}
        for directory, recursive in source_directories:
            unique_directories.setdefault(directory, recursive)
        source_directories = list(unique_directories.items())
        if not source_directories:
            self.report({"ERROR"}, "Add an existing Shared Textures directory in Sollumz preferences first.")
            return {"CANCELLED"}

        try:
            find_bridge_command(preferences.cwbridge_executable)
        except CWBridgeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        cache_path = bpy.utils.user_resource(
            resource_type="CONFIG",
            path="resollumz/ytd_textures",
            create=True,
        )
        if not cache_path:
            self.report({"ERROR"}, "Could not resolve the Blender configuration directory for the YTD texture cache.")
            return {"CANCELLED"}

        requests = [
            (node, texture_name, model_names)
            for node, texture_name, model_names in targets
        ]
        self._targets = requests
        executable_path = preferences.cwbridge_executable
        gen9 = self.gen9
        force_reindex = self.force_reindex
        cache_directory = Path(cache_path)
        result_queue = queue.Queue()
        self._progress_queue = queue.Queue()
        progress_queue = self._progress_queue
        self._result_queue = result_queue
        self._cancel_event = threading.Event()
        cancel_event = self._cancel_event
        self._progress_active = False
        source_count = len(source_directories)

        def index_folder():
            try:
                textures = []
                errors = []
                indexed = 0
                for source_index, (source_path, recursive) in enumerate(source_directories):
                    if cancel_event.is_set():
                        raise CWBridgeCancelled("YTD indexing was cancelled.")

                    def report_progress(completed, total, *, index=source_index, path=source_path):
                        fraction = (index + completed / total) / source_count if total else index / source_count
                        progress_queue.put((fraction, str(path), completed, total))

                    result = index_ytd_directory(
                        source_path,
                        cache_directory,
                        gen9=gen9,
                        executable_path=executable_path,
                        recursive=recursive,
                        force_reindex=force_reindex,
                        cancel_event=cancel_event,
                        progress_callback=report_progress,
                    )
                    textures.extend(result.textures)
                    errors.extend(result.errors)
                    indexed += result.indexed_dictionaries
                    progress_queue.put(((source_index + 1) / source_count, str(source_path), 0, 0))

                result_queue.put(YtdIndexResult(tuple(textures), indexed, tuple(errors)))
            except Exception as exc:
                result_queue.put(exc)

        self._worker = threading.Thread(target=index_folder, name="RESollumzYtdIndex", daemon=True)
        self._worker.start()
        context.window_manager.progress_begin(0, 1)
        self._progress_active = True
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._cancel_event.set()
            self.report({"INFO"}, "Cancelling YTD indexing...")
            return {"RUNNING_MODAL"}
        if event.type == "TIMER":
            self._update_progress(context)
        if event.type != "TIMER" or self._worker.is_alive():
            return {"PASS_THROUGH"}

        self._finish_progress(context)
        result = self._result_queue.get()
        if isinstance(result, Exception):
            if isinstance(result, CWBridgeCancelled):
                self.report({"INFO"}, "YTD indexing cancelled.")
                return {"CANCELLED"}
            logger.error(f"Failed to index YTD textures: {result}")
            self.report({"ERROR"}, str(result))
            return {"CANCELLED"}

        linked = self._link_indexed_textures(result)
        for error in result.errors:
            logger.warning(f"Could not index YTD texture dictionary: {error}")

        if result.indexed_dictionaries == 0 and not result.errors:
            self.report({"WARNING"}, "No .ytd files were found in the selected folder.")
            return {"CANCELLED"}
        message = (
            f"Linked {linked} texture(s) from {result.indexed_dictionaries} YTD file(s); "
            f"{len(result.errors)} dictionary error(s)."
        )
        if result.errors:
            logger.warning(f"YTD indexing failed for {len(result.errors)} file(s). First error: {result.errors[0]}")
        self.report({"WARNING"} if result.errors else {"INFO"}, message)
        return {"FINISHED"}

    def cancel(self, context):
        if hasattr(self, "_cancel_event"):
            self._cancel_event.set()
        if hasattr(self, "_timer") and self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._finish_progress(context)

    def _update_progress(self, context):
        while True:
            try:
                fraction, directory, completed, total = self._progress_queue.get_nowait()
            except queue.Empty:
                break
            context.window_manager.progress_update(fraction)
            if context.workspace is not None:
                status = f"Indexing YTDs: {completed}/{total}" if total else "Indexing YTDs"
                context.workspace.status_text_set(f"{status} — {directory}")

    def _finish_progress(self, context):
        timer = getattr(self, "_timer", None)
        if timer is not None:
            context.window_manager.event_timer_remove(timer)
            self._timer = None
        if self._progress_active:
            context.window_manager.progress_end()
            self._progress_active = False
        if context.workspace is not None:
            context.workspace.status_text_set(None)

    def _link_indexed_textures(self, result: YtdIndexResult) -> int:
        linked = 0
        for node, texture_name, model_names in self._targets:
            match = choose_texture(result.textures, texture_name, model_names)
            if match is None:
                continue
            try:
                image = bpy.data.images.load(str(match.path), check_existing=True)
            except RuntimeError as exc:
                logger.warning(f"Could not load YTD texture '{match.name}' from '{match.path}': {exc}")
                continue
            node.image = image
            material = getattr(node, "id_data", None)
            shader_properties = getattr(material, "shader_properties", None)
            shader_filename = getattr(shader_properties, "filename", "")
            from ...ydr.ydrimport import is_non_color_texture

            if is_non_color_texture(shader_filename, node.name):
                image.colorspace_settings.is_data = True
            linked += 1
        return linked


def _selected_missing_texture_samplers(context):
    pending = list(context.selected_objects or ())
    seen_objects = set()
    targets = []
    while pending:
        obj = pending.pop()
        pointer = obj.as_pointer()
        if pointer in seen_objects:
            continue
        seen_objects.add(pointer)
        pending.extend(obj.children)

        model_names = []
        parent = obj
        while parent is not None:
            model_names.append(parent.name)
            parent = parent.parent

        for material in getattr(getattr(obj, "data", None), "materials", ()):
            if material is None or material.node_tree is None:
                continue
            for node in material.node_tree.nodes:
                if not isinstance(node, bpy.types.ShaderNodeTexImage):
                    continue
                if not hasattr(node, "sollumz_texture_name"):
                    continue
                texture_name = node.sollumz_texture_name
                if not texture_name or not _image_is_missing(node.image):
                    continue
                targets.append((node, texture_name, tuple(model_names)))
    return targets


def _image_is_missing(image):
    if image is None:
        return False
    if image.source != "FILE" or image.packed_files:
        return False
    path = bpy.path.abspath(image.filepath, library=image.library)
    return not path or not os.path.isfile(path)


class SOLLUMZ_OT_import_ytd(ImportAssetsOperatorImpl, Operator):
    """Import texture dictionaries (.ytd)"""

    bl_idname = "sollumz.import_ytd"
    bl_label = "Import YTD"
    bl_options = {"UNDO"}

    filter_glob: StringProperty(
        default="*.ytd;*.ytd.xml",
        options={"HIDDEN", "SKIP_SAVE"},
        maxlen=255,
    )


class SOLLUMZ_OT_export_ytd(ExportAssetsOperatorImpl, Operator):
    """Export the selected texture dictionaries"""

    bl_idname = "sollumz.export_ytd"
    bl_label = "Export YTD"
    sz_export_types = {"YTD"}

    @classmethod
    def poll(cls, context):
        return context.scene.sz_txds.texture_dictionaries
