from pathlib import Path


def data_root() -> Path:
    import bpy

    path = bpy.utils.user_resource("CONFIG", path="resollumz", create=True)
    if not path:
        raise OSError("Blender did not provide a user configuration directory.")
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def versions_root() -> Path:
    path = data_root() / "versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_path() -> Path:
    return data_root() / "release-catalog.json"


def state_path() -> Path:
    return data_root() / "loader-state.json"
