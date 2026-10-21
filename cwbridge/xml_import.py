import shutil
from pathlib import Path
from xml.etree import ElementTree

from .client import CWBridgeError


def stage_xml_for_import(xml_path: Path, staging_directory: Path, resource_format: str) -> Path:
    xml_path = xml_path.resolve()
    staging_directory = staging_directory.resolve()
    staging_directory.mkdir(parents=True, exist_ok=True)
    staged_xml = staging_directory / xml_path.name
    shutil.copy2(xml_path, staged_xml)

    try:
        xml_root = ElementTree.parse(xml_path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise CWBridgeError(f"Could not read CodeWalker XML: {exc}") from exc

    asset_name = xml_path.stem
    if asset_name.casefold().endswith(f".{resource_format}"):
        asset_name = asset_name[:-(len(resource_format) + 1)]
    asset_directory = xml_path.parent / asset_name
    staged_textures = set()

    for node in xml_root.iter("FileName"):
        filename = (node.text or "").strip()
        if not filename.casefold().endswith(".dds"):
            continue
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or ":" in filename
        ):
            raise CWBridgeError(f"Unsafe texture path in CodeWalker XML: {filename}")
        if filename in staged_textures:
            continue

        texture_path = next(
            (
                candidate
                for candidate in (xml_path.parent / filename, asset_directory / filename)
                if candidate.is_file()
            ),
            None,
        )
        if texture_path is None:
            raise CWBridgeError(f"Referenced texture file not found: {filename}")

        shutil.copy2(texture_path, staging_directory / filename)
        staged_textures.add(filename)

    return staged_xml
