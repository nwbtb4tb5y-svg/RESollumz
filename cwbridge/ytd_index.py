import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .client import CWBridgeCancelled, CWBridgeError, convert_file, find_bridge_command


@dataclass(frozen=True)
class IndexedTexture:
    name: str
    path: Path
    dictionary_name: str


@dataclass(frozen=True)
class YtdIndexResult:
    textures: tuple[IndexedTexture, ...]
    indexed_dictionaries: int
    errors: tuple[str, ...]


def index_ytd_directory(
    source_directory: Path,
    cache_directory: Path,
    *,
    gen9: bool = False,
    executable_path: str | None = None,
    recursive: bool = True,
    force_reindex: bool = False,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> YtdIndexResult:
    source_directory = source_directory.resolve()
    if not source_directory.is_dir():
        raise CWBridgeError(f"YTD source directory does not exist: {source_directory}")

    bridge_command = find_bridge_command(executable_path)
    cache_directory.mkdir(parents=True, exist_ok=True)
    textures: list[IndexedTexture] = []
    errors: list[str] = []
    indexed = 0
    ytd_paths = sorted(
        source_directory.rglob("*.ytd") if recursive else source_directory.glob("*.ytd"),
        key=lambda path: str(path).casefold(),
    )

    if progress_callback is not None:
        progress_callback(0, len(ytd_paths))

    for completed, ytd_path in enumerate(ytd_paths, start=1):
        if cancel_event is not None and cancel_event.is_set():
            raise CWBridgeCancelled("YTD indexing was cancelled.")
        try:
            dictionary_textures = _index_ytd(
                ytd_path.resolve(),
                cache_directory,
                gen9=gen9,
                executable_path=executable_path,
                bridge_command=bridge_command,
                force_reindex=force_reindex,
                cancel_event=cancel_event,
            )
        except CWBridgeCancelled:
            raise
        except (OSError, ValueError, CWBridgeError) as exc:
            errors.append(f"{ytd_path}: {exc}")
            if progress_callback is not None:
                progress_callback(completed, len(ytd_paths))
            continue
        textures.extend(dictionary_textures)
        indexed += 1
        if progress_callback is not None:
            progress_callback(completed, len(ytd_paths))

    if cancel_event is not None and cancel_event.is_set():
        raise CWBridgeCancelled("YTD indexing was cancelled.")

    return YtdIndexResult(tuple(textures), indexed, tuple(errors))


def _index_ytd(
    ytd_path: Path,
    cache_directory: Path,
    *,
    gen9: bool,
    executable_path: str | None,
    bridge_command: list[str],
    force_reindex: bool,
    cancel_event: threading.Event | None,
) -> list[IndexedTexture]:
    stat = ytd_path.stat()
    source_key = hashlib.sha256(os.path.normcase(str(ytd_path)).encode("utf-8")).hexdigest()
    dictionary_cache = cache_directory / source_key
    if dictionary_cache.is_symlink():
        raise CWBridgeError(f"Refusing to use a symlink in the YTD cache: {dictionary_cache}")
    metadata_path = dictionary_cache / "source.json"
    metadata = {
        "path": str(ytd_path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "gen9": gen9,
    }

    if not force_reindex and _cache_matches(dictionary_cache, metadata_path, metadata):
        return _cached_textures(dictionary_cache, ytd_path.stem)

    staging = Path(tempfile.mkdtemp(prefix=f".{source_key}.", dir=cache_directory))
    try:
        xml_path = staging / f"{ytd_path.stem}.xml"
        convert_file(
            ytd_path,
            xml_path,
            operation="to_xml",
            gen9=gen9,
            include_textures=True,
            executable_path=executable_path,
            bridge_command=bridge_command,
            cancel_event=cancel_event,
        )
        if cancel_event is not None and cancel_event.is_set():
            raise CWBridgeCancelled("YTD indexing was cancelled.")
        try:
            xml_root = ElementTree.parse(xml_path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise CWBridgeError(f"CWBridge produced invalid YTD XML: {exc}") from exc
        for filename in (node.text for node in xml_root.iter("FileName")):
            if not filename:
                continue
            texture_path = (staging / filename).resolve()
            if not texture_path.is_relative_to(staging.resolve()):
                raise CWBridgeError(f"YTD XML contains an unsafe texture path: {filename}")
            if not texture_path.is_file():
                raise CWBridgeError(f"CWBridge did not extract referenced texture: {filename}")
        (staging / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
        if cancel_event is not None and cancel_event.is_set():
            raise CWBridgeCancelled("YTD indexing was cancelled.")
        backup = None
        if dictionary_cache.exists():
            if dictionary_cache.is_symlink():
                raise CWBridgeError(f"Refusing to replace a symlink in the YTD cache: {dictionary_cache}")
            backup = cache_directory / f".{source_key}.{uuid.uuid4().hex}.backup"
            os.replace(dictionary_cache, backup)
        try:
            os.replace(staging, dictionary_cache)
        except Exception:
            if backup is not None:
                os.replace(backup, dictionary_cache)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return _cached_textures(dictionary_cache, ytd_path.stem)


def _cache_matches(cache_directory: Path, metadata_path: Path, expected: dict) -> bool:
    try:
        actual = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if actual != expected:
        return False
    xml_files = tuple(cache_directory.glob("*.xml"))
    if not xml_files:
        return False
    try:
        for xml_path in xml_files:
            xml_root = ElementTree.parse(xml_path).getroot()
            for filename in (node.text for node in xml_root.iter("FileName")):
                if not filename:
                    continue
                texture_path = (cache_directory / filename).resolve()
                if not texture_path.is_relative_to(cache_directory.resolve()) or not texture_path.is_file():
                    return False
    except (OSError, ElementTree.ParseError):
        return False
    return True


def _cached_textures(cache_directory: Path, dictionary_name: str) -> list[IndexedTexture]:
    return [
        IndexedTexture(path.stem.casefold(), path, dictionary_name)
        for path in sorted(cache_directory.glob("*.dds"), key=lambda item: item.name.casefold())
    ]


def choose_texture(
    candidates: tuple[IndexedTexture, ...] | list[IndexedTexture],
    texture_name: str,
    model_names: tuple[str, ...] | list[str],
) -> IndexedTexture | None:
    texture_name = texture_name.casefold()
    matching = [item for item in candidates if item.name.casefold() == texture_name]
    if not matching:
        return None

    by_dictionary: dict[str, list[IndexedTexture]] = {}
    for item in matching:
        by_dictionary.setdefault(_normalize_dictionary_name(item.dictionary_name), []).append(item)

    model_keys = {_normalize_dictionary_name(name) for name in model_names}
    preferred = [items for dictionary_name, items in by_dictionary.items() if dictionary_name in model_keys]
    if preferred:
        matching = [item for items in preferred for item in items]
    elif len(by_dictionary) > 1:
        return None

    high_resolution = [
        item for item in matching
        if Path(item.dictionary_name).stem.casefold().endswith(("+hi", "+hidr", "+hifr", "+hidd"))
    ]
    if high_resolution:
        matching = high_resolution

    unique_paths = {item.path.resolve(): item for item in matching}
    return next(iter(unique_paths.values())) if len(unique_paths) == 1 else None


def _normalize_dictionary_name(name: str) -> str:
    normalized = Path(name).stem.casefold()
    for suffix in ("+hi", "+hidr", "+hifr", "+hidd"):
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
            break
    return normalized
