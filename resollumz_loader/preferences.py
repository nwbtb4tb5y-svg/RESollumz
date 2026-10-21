import logging
import os

import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy.types import AddonPreferences, Operator

from .core import catalog, github, jobs, manager, runtime
from .core.paths import catalog_path, state_path, versions_root


_logger = logging.getLogger("resollumz_loader.preferences")


def _version_items(self, context):
    installed = set(manager.installed_versions(versions_root()))
    tags = set(installed)
    try:
        tags.update(release["tag"] for release in catalog.read_catalog(catalog_path()))
    except github.ReleaseError as exc:
        _logger.error("Could not populate release selector: %s", exc)
        jobs.state.message = str(exc)
        jobs.state.error = True
    return [
        (tag, tag, f"{tag}{' (installed)' if tag in installed else ''}")
        for tag in manager.sort_versions(tags)
    ]


class RESOLLUMZ_Preferences(AddonPreferences):
    bl_idname = __package__

    allow_network_access: BoolProperty(
        name="Allow network access",
        description="Allow explicit requests to refresh GitHub releases and download Sollumz archives",
        default=False,
    )
    selected_version: EnumProperty(name="Sollumz release", items=_version_items)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "allow_network_access")
        layout.label(text="Optional: set GITHUB_TOKEN in the environment to increase GitHub API limits.", icon="INFO")

        installed = manager.installed_versions(versions_root())
        try:
            state = catalog.read_state(state_path())
        except github.ReleaseError as exc:
            state = {}
            jobs.state.message = str(exc)
            jobs.state.error = True
        active = runtime.active_tag() or state.get("active_tag") or "None"
        layout.label(text=f"Active release: {active}")
        box = layout.box()
        box.label(text="Installed releases")
        if installed:
            for tag in installed:
                marker = "CHECKMARK" if tag == active else "DOT"
                box.label(text=tag, icon=marker)
        else:
            box.label(text="No releases installed yet.", icon="INFO")

        layout.prop(self, "selected_version")
        row = layout.row(align=True)
        row.enabled = not jobs.state.busy
        row.operator(RESOLLUMZ_OT_refresh_releases.bl_idname, icon="FILE_REFRESH")
        row.operator(RESOLLUMZ_OT_install_activate.bl_idname, icon="IMPORT")
        row = layout.row(align=True)
        row.enabled = not jobs.state.busy
        row.operator(RESOLLUMZ_OT_activate_installed.bl_idname, icon="PLAY")
        row.operator(RESOLLUMZ_OT_remove_release.bl_idname, icon="TRASH")

        status = layout.row()
        status.alert = jobs.state.error
        status.label(text=jobs.state.message, icon="ERROR" if jobs.state.error else "INFO")
        if jobs.state.busy:
            layout.label(text="The operation runs in the background; Blender remains responsive.", icon="TIME")
        elif state.get("last_error"):
            layout.label(text=state["last_error"], icon="ERROR")


class _BackgroundJobMixin:
    def invoke(self, context, event):
        if not _network_allowed(self, context):
            return {"CANCELLED"}
        try:
            job = self.create_job(context)
        except Exception as exc:
            _logger.exception("Could not start background operation")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if not jobs.start(job):
            self.report({"ERROR"}, "Another release operation is already running.")
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self.report({"INFO"}, "The current operation continues in the background.")
            return {"RUNNING_MODAL"}
        if event.type != "TIMER" or jobs.state.busy:
            return {"PASS_THROUGH"}

        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        succeeded, message = jobs.finish_pending()
        self.report({"INFO"} if succeeded else {"ERROR"}, message)
        return {"FINISHED"} if succeeded else {"CANCELLED"}

    def create_job(self, context):
        raise NotImplementedError


class RESOLLUMZ_OT_refresh_releases(_BackgroundJobMixin, Operator):
    bl_idname = "resollumz.refresh_releases"
    bl_label = "Refresh Release List"
    bl_description = "Fetch official Sollumz releases from GitHub"

    def create_job(self, context):
        token = self.get_token(context)
        release_catalog_path = catalog_path()

        def refresh():
            releases = github.fetch_releases(token)
            catalog.write_catalog(release_catalog_path, releases)
            return f"Release list updated ({len(releases)} releases)."

        return refresh

    @staticmethod
    def get_token(context):
        return os.environ.get("GITHUB_TOKEN", "").strip()


class RESOLLUMZ_OT_install_activate(_BackgroundJobMixin, Operator):
    bl_idname = "resollumz.install_activate"
    bl_label = "Download / Install and Activate"
    bl_description = "Download the selected official release, verify it, and install it"

    def create_job(self, context):
        prefs = context.preferences.addons[__package__].preferences
        tag = prefs.selected_version
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        release_catalog_path = catalog_path()
        root = versions_root()
        releases = catalog.read_catalog(release_catalog_path)
        release = next((item for item in releases if item.get("tag") == tag), None)
        if release is None:
            raise github.ReleaseError("Refresh the release list and select an available Sollumz version first.")
        if tag in manager.installed_versions(versions_root()):
            raise github.ReleaseError(f"Sollumz {tag} is already installed; use Activate Installed.")

        def install():
            archive = github.download_release(release, token)
            package = manager.install_archive(root, tag, archive, release.get("sha256"))
            digest_warning = " No SHA-256 digest was published for this release." if not release.get("sha256") else ""
            return f"Sollumz {tag} was installed at {package}.{digest_warning}"

        return install

    def invoke(self, context, event):
        if not _network_allowed(self, context):
            return {"CANCELLED"}
        tag = context.preferences.addons[__package__].preferences.selected_version
        if not tag:
            self.report({"ERROR"}, "Select a release first.")
            return {"CANCELLED"}

        self._tag = tag
        try:
            job = self.create_job(context)
        except Exception as exc:
            _logger.exception("Could not prepare the Sollumz release download")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if not jobs.start(job):
            self.report({"ERROR"}, "Another release operation is already running.")
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self.report({"INFO"}, "The download continues in the background.")
            return {"RUNNING_MODAL"}
        if event.type != "TIMER" or jobs.state.busy:
            return {"PASS_THROUGH"}

        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        succeeded, message = jobs.finish_pending(
            on_success=lambda: runtime.activate(self._tag)
        )
        self.report({"INFO"} if succeeded else {"ERROR"}, message)
        return {"FINISHED"} if succeeded else {"CANCELLED"}


class RESOLLUMZ_OT_activate_installed(Operator):
    bl_idname = "resollumz.activate_installed"
    bl_label = "Activate Installed Release"
    bl_description = "Activate the selected installed Sollumz release"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        tag = prefs.selected_version
        if not tag or tag not in manager.installed_versions(versions_root()):
            self.report({"ERROR"}, "The selected Sollumz release is not installed.")
            return {"CANCELLED"}
        try:
            message = runtime.activate(tag)
        except Exception as exc:
            _logger.exception("Could not activate Sollumz %s", tag)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, message)
        return {"FINISHED"}


class RESOLLUMZ_OT_remove_release(Operator):
    bl_idname = "resollumz.remove_release"
    bl_label = "Remove Installed Release"
    bl_description = "Remove the selected cached Sollumz release"

    @classmethod
    def poll(cls, context):
        prefs = context.preferences.addons.get(__package__)
        return prefs is not None and bool(prefs.preferences.selected_version)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        tag = prefs.selected_version
        if tag not in manager.installed_versions(versions_root()):
            self.report({"ERROR"}, "The selected release is not installed.")
            return {"CANCELLED"}
        state = catalog.read_state(state_path())
        if tag == state.get("active_tag") or tag == runtime.active_tag():
            self.report({"ERROR"}, "The active release cannot be removed. Activate another release and restart first.")
            return {"CANCELLED"}
        try:
            manager.remove_release(versions_root(), tag)
        except Exception as exc:
            _logger.exception("Could not remove Sollumz %s", tag)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Sollumz {tag} was removed.")
        return {"FINISHED"}


CLASSES = (
    RESOLLUMZ_Preferences,
    RESOLLUMZ_OT_refresh_releases,
    RESOLLUMZ_OT_install_activate,
    RESOLLUMZ_OT_activate_installed,
    RESOLLUMZ_OT_remove_release,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


def _network_allowed(operator, context):
    prefs = context.preferences.addons[__package__].preferences
    if not prefs.allow_network_access:
        operator.report({"ERROR"}, "Enable Allow network access in RESollumz Loader preferences first.")
        return False
    if hasattr(bpy.app, "online_access") and not bpy.app.online_access:
        operator.report({"ERROR"}, "Blender online access is disabled in System Preferences.")
        return False
    return True
