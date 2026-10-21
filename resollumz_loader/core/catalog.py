import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .github import ReleaseError


def read_catalog(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"Could not read cached release list: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("releases"), list):
        raise ReleaseError("Cached release list has an invalid format.")
    return value["releases"]


def write_catalog(path: Path, releases: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"updated_at": datetime.now(timezone.utc).isoformat(), "releases": releases},
        indent=2,
        ensure_ascii=False,
    )
    _atomic_write(path, payload)


def read_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"Could not read loader state: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError("Loader state has an invalid format.")
    return value


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(state, indent=2, ensure_ascii=False))


def _atomic_write(path: Path, content: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except OSError:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
