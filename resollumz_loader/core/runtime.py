import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType

from .catalog import read_state, write_state
from .github import ReleaseError
from .manager import installed_package_path, module_name
from .paths import state_path, versions_root


_logger = logging.getLogger("resollumz_loader.runtime")
_active_module: ModuleType | None = None
_active_tag: str | None = None


def active_tag() -> str | None:
    return _active_tag


def ensure_addon_preferences_entry(module_name: str) -> None:
    import bpy

    addons = bpy.context.preferences.addons
    existing = addons.get(module_name)
    if existing is not None:
        return
    for candidate in list(addons):
        if getattr(candidate, "module", None) == module_name:
            return
    entry = addons.new()
    entry.module = module_name


def remove_addon_preferences_entry(module_name: str) -> None:
    import bpy

    addons = bpy.context.preferences.addons
    existing = addons.get(module_name)
    if existing is not None:
        addons.remove(existing)
        return
    for candidate in list(addons):
        if getattr(candidate, "module", None) == module_name:
            addons.remove(candidate)
            return


def activate_on_startup() -> None:
    try:
        state = read_state(state_path())
        tag = state.get("active_tag")
        if not tag:
            return
        activate(tag, startup=True)
    except Exception as exc:
        _logger.exception("Failed to activate the configured Sollumz release")
        try:
            state = read_state(state_path())
        except ReleaseError:
            state = {}
        state["last_error"] = f"Could not load Sollumz: {exc}"
        write_state(state_path(), state)


def activate(tag: str, startup: bool = False) -> str:
    global _active_module, _active_tag
    package_path = installed_package_path(versions_root(), tag)
    if _active_tag == tag and _active_module is not None:
        return "Sollumz version is already active."
    if _active_module is not None and not startup:
        state = read_state(state_path())
        state["active_tag"] = tag
        state.pop("last_error", None)
        write_state(state_path(), state)
        return f"Sollumz {tag} is selected and will be activated after restarting Blender."
    if _has_external_sollumz_instance():
        raise ReleaseError(
            "Another Sollumz instance is active. Disable the ordinary Sollumz add-on, restart Blender, "
            "and activate the managed release again."
        )

    package_module_name = module_name(tag)
    data_path = versions_root() / tag / "data"
    module = _load_package(package_module_name, package_path, data_path)
    try:
        ensure_addon_preferences_entry(package_module_name)
        import addon_utils

        addon_utils.modules_refresh()
        module = sys.modules.get(package_module_name, module)
        _isolate_dependencies(module, data_path)
        enabled_module = addon_utils.enable(package_module_name, default_set=False)
        if enabled_module is None:
            raise ReleaseError(f"Blender could not register the Sollumz {tag} add-on.")
        module = enabled_module
        _isolate_dependencies(module, data_path)
    except Exception as exc:
        _active_module = module
        _active_tag = tag
        raise ReleaseError(
            f"Sollumz {tag} failed during registration. Blender may have partial registrations; restart Blender "
            "before trying another release."
        ) from exc

    _active_module = module
    _active_tag = tag
    state = read_state(state_path())
    state["active_tag"] = tag
    state.pop("last_error", None)
    write_state(state_path(), state)
    return f"Sollumz {tag} is active."


def deactivate() -> str:
    global _active_module, _active_tag
    if _active_module is None:
        return "No managed Sollumz release is loaded."
    package_module_name = _active_module.__name__
    try:
        import addon_utils

        addon_utils.disable(package_module_name, default_set=False)
    except Exception:
        _logger.exception("Could not cleanly unregister managed Sollumz %s", _active_tag)
        raise
    remove_addon_preferences_entry(package_module_name)
    _remove_package_modules(package_module_name)
    module_parent = str(Path(_active_module.__file__).parent.parent)
    if module_parent in sys.path:
        sys.path.remove(module_parent)
    _active_module = None
    _active_tag = None
    return "Managed Sollumz was unregistered."


def _load_package(module_name: str, package_path: Path, data_path: Path) -> ModuleType:
    module_parent = str(package_path.parent)
    added_module_parent = module_parent not in sys.path
    if added_module_parent:
        sys.path.insert(0, module_parent)
    try:
        module = importlib.import_module(module_name)
        _isolate_dependencies(module, data_path)
    except Exception:
        _remove_package_modules(module_name)
        if added_module_parent and module_parent in sys.path:
            sys.path.remove(module_parent)
        raise
    return module


def _isolate_dependencies(module: ModuleType, data_path: Path) -> None:
    dependencies = sys.modules.get(f"{module.__name__}.dependencies")
    if dependencies is None:
        return
    if not (Path(module.__path__[0]) / "known_paths.py").is_file():
        raise ReleaseError("Sollumz dependency manager exists but known_paths.py is missing.")
    known_paths = importlib.import_module(".known_paths", module.__name__)
    data_path.mkdir(parents=True, exist_ok=True)

    def version_data_directory() -> str:
        return str(data_path)

    def version_site_packages() -> Path:
        version = sys.version_info
        return data_path / "lib" / f"python{version.major}.{version.minor}" / "site-packages"

    def version_requirements_file() -> Path:
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path / "requirements.txt"

    known_paths.data_directory_path = version_data_directory
    dependencies.data_directory_path = version_data_directory
    dependencies.site_packages_path = version_site_packages
    if hasattr(dependencies, "requirements_path"):
        dependencies.requirements_path = version_requirements_file


def _remove_package_modules(module_name: str) -> None:
    for name in tuple(sys.modules):
        if name == module_name or name.startswith(module_name + "."):
            del sys.modules[name]


def _has_external_sollumz_instance() -> bool:
    import bpy

    return hasattr(bpy.types.Object, "sollum_type")
