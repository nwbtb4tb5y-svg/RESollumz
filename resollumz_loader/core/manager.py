import hashlib
import io
import os
import re
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .github import ReleaseError, validate_tag


MAX_ARCHIVE_FILES = 20_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
_SAFE_TAG = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_VERSION_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9.-]+))?$")


def installed_versions(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sort_versions(
        path.name for path in root.iterdir()
        if path.is_dir() and _SAFE_TAG.fullmatch(path.name)
    )


def sort_versions(tags: Iterable[str]) -> list[str]:
    return sorted(tags, key=_version_sort_key, reverse=True)


def installed_package_path(root: Path, tag: str) -> Path:
    validate_tag(tag)
    release_dir = (root / tag).resolve()
    if release_dir.parent != root.resolve():
        raise ReleaseError("Release path escaped the managed versions directory.")
    candidates = [release_dir / module_name(tag), release_dir / "Sollumz", release_dir]
    for candidate in candidates:
        if (candidate / "__init__.py").is_file():
            return candidate
    raise ReleaseError(f"Installed release {tag} does not contain a Sollumz add-on package.")


def install_archive(root: Path, tag: str, archive: bytes, expected_sha256: str | None) -> Path:
    validate_tag(tag)
    if expected_sha256 is not None:
        actual = hashlib.sha256(archive).hexdigest()
        if not _constant_time_equal(actual, expected_sha256.lower()):
            raise ReleaseError(f"SHA-256 verification failed for Sollumz {tag}.")

    root.mkdir(parents=True, exist_ok=True)
    final_dir = root / tag
    if final_dir.exists():
        raise ReleaseError(f"Sollumz {tag} is already installed.")
    staging = Path(tempfile.mkdtemp(prefix=f".{tag}.", dir=root))
    try:
        _extract_validated(archive, staging)
        package = _find_package_root(staging)
        if not (package / "auto_load.py").is_file():
            raise ReleaseError(f"Sollumz {tag} is missing its add-on module loader.")
        destination = staging / module_name(tag)
        if package != destination:
            if destination.exists():
                raise ReleaseError("Release archive contains multiple Sollumz package roots.")
            package.rename(destination)
        os.replace(staging, final_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return final_dir / module_name(tag)


def remove_release(root: Path, tag: str) -> None:
    validate_tag(tag)
    root_resolved = root.resolve()
    release_dir = root / tag
    if not release_dir.exists():
        raise ReleaseError(f"Sollumz {tag} is not installed.")
    if release_dir.is_symlink() or release_dir.resolve().parent != root_resolved:
        raise ReleaseError("Refusing to remove a release path outside the managed versions directory.")
    shutil.rmtree(release_dir)


def _extract_validated(archive: bytes, destination: Path) -> None:
    try:
        source = zipfile.ZipFile(io.BytesIO(archive))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseError(f"Downloaded release is not a valid ZIP archive: {exc}") from exc
    with source:
        infos = source.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_FILES:
            raise ReleaseError("Release archive has an invalid number of entries.")
        total_size = 0
        validated = []
        for info in infos:
            normalized = info.filename.replace("\\", "/")
            relative = PurePosixPath(normalized)
            mode = info.external_attr >> 16
            if (
                not normalized
                or relative.is_absolute()
                or any(part in {"", ".", ".."} for part in relative.parts)
                or (relative.parts and ":" in relative.parts[0])
                or stat.S_ISLNK(mode)
            ):
                raise ReleaseError(f"Unsafe path in release archive: {info.filename!r}")
            total_size += info.file_size
            if info.file_size < 0 or total_size > MAX_UNCOMPRESSED_BYTES:
                raise ReleaseError("Release archive exceeds the 500 MiB extraction limit.")
            validated.append((info, relative))

        for info, relative in validated:
            path = destination.joinpath(*relative.parts)
            resolved = path.resolve()
            if not resolved.is_relative_to(destination.resolve()):
                raise ReleaseError(f"Unsafe destination path in release archive: {info.filename!r}")
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as input_stream, path.open("xb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def _find_package_root(staging: Path) -> Path:
    candidates = []
    if (staging / "__init__.py").is_file():
        candidates.append(staging)
    candidates.extend(
        path for path in staging.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    if len(candidates) != 1:
        raise ReleaseError("Release ZIP must contain exactly one top-level add-on package.")
    return candidates[0]


def module_name(tag: str) -> str:
    validate_tag(tag)
    return "_resollumz_managed_sollumz_" + re.sub(r"[^A-Za-z0-9_]", "_", tag)


def _constant_time_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def _version_sort_key(tag: str) -> tuple[int, int, int, int, int, str]:
    match = _VERSION_TAG.fullmatch(tag)
    if match is None:
        return (0, 0, 0, 0, 0, tag.lower())
    major, minor, patch = (int(part) for part in match.groups()[:3])
    prerelease = match.group(4)
    return (1, major, minor, patch, int(prerelease is None), prerelease or "")
