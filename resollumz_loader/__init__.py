import logging

from .core import runtime


bl_info = {
    "name": "RESollumz Loader",
    "author": "nwbtb4tb5y-svg",
    "description": "Manage and load official Sollumz releases",
    "blender": (4, 2, 0),
    "version": (0, 1, 0),
    "category": "Import-Export",
}

_logger = logging.getLogger("resollumz_loader")


def register():
    from . import preferences

    preferences.register()
    runtime.ensure_addon_preferences_entry(__package__)
    runtime.activate_on_startup()


def unregister():
    from . import preferences

    try:
        runtime.deactivate()
    finally:
        preferences.unregister()
