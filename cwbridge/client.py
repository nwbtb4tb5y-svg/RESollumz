import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class CWBridgeError(RuntimeError):
    pass


class CWBridgeCancelled(CWBridgeError):
    pass


def find_bridge_command(configured_path: str | None = None) -> list[str]:
    candidates = []
    if configured_path and configured_path.strip():
        candidates.append(Path(configured_path).expanduser())
    if environment_path := os.environ.get("RESOLLUMZ_CWBRIDGE", "").strip():
        candidates.append(Path(environment_path).expanduser())

    bridge_directory = Path(__file__).resolve().parent
    candidates.extend((
        bridge_directory / "publish" / "CWBridge.exe",
        bridge_directory / "publish" / "CWBridge",
        bridge_directory / "bin" / "Release" / "net8.0" / "win-x64" / "publish" / "CWBridge.exe",
        bridge_directory / "bin" / "Release" / "net8.0" / "linux-x64" / "publish" / "CWBridge",
        bridge_directory / "bin" / "Release" / "net8.0" / "osx-x64" / "publish" / "CWBridge",
        bridge_directory / "bin" / "Release" / "net8.0" / "CWBridge.exe",
        bridge_directory / "bin" / "Release" / "net8.0" / "CWBridge",
        bridge_directory / "bin" / "Release" / "net8.0" / "CWBridge.dll",
    ))

    for candidate in candidates:
        path = candidate.resolve()
        if not path.is_file():
            continue
        if path.suffix.lower() == ".dll":
            dotnet = shutil.which("dotnet")
            if dotnet is None:
                raise CWBridgeError("CWBridge is a .NET DLL, but the .NET 8 runtime was not found on PATH.")
            return [dotnet, str(path)]
        if os.name == "nt" and path.suffix.lower() not in {".exe", ".com"}:
            continue
        if not os.access(path, os.X_OK) and os.name != "nt":
            continue
        return [str(path)]

    configured = f" Configured path: {configured_path}." if configured_path else ""
    raise CWBridgeError(
        "CWBridge executable was not found. Build or publish cwbridge and set its path in Sollumz "
        f"preferences.{configured}"
    )


def convert_file(
    input_path: Path,
    output_path: Path,
    *,
    operation: str,
    gen9: bool = False,
    include_textures: bool = True,
    executable_path: str | None = None,
    bridge_command: list[str] | None = None,
    timeout: float = 600,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    command = bridge_command or find_bridge_command(executable_path)
    request = {
        "operation": operation,
        "inputPath": str(input_path.resolve()),
        "outputPath": str(output_path.resolve()),
        "gen9": gen9,
        "includeTextures": include_textures,
    }
    result = _run_bridge(command, json.dumps(request), timeout, cancel_event)

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        diagnostics = result.stderr.strip()
        detail = f" Bridge diagnostics: {diagnostics}" if diagnostics else ""
        raise CWBridgeError(f"CWBridge returned invalid JSON (exit code {result.returncode}).{detail}") from exc

    if not isinstance(response, dict):
        raise CWBridgeError("CWBridge returned a JSON response that is not an object.")
    if result.returncode != 0 or not response.get("ok"):
        error = response.get("error")
        if isinstance(error, dict):
            code = error.get("code", "unknown_error")
            message = error.get("message", "No error message was returned.")
            raise CWBridgeError(f"CWBridge {code}: {message}")
        raise CWBridgeError(f"CWBridge failed with exit code {result.returncode}.")

    if Path(response.get("outputPath", "")).resolve() != output_path.resolve():
        raise CWBridgeError("CWBridge response output path does not match the requested output.")
    return response


def _run_bridge(
    command: list[str],
    request: str,
    timeout: float,
    cancel_event: threading.Event | None,
) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise CWBridgeError(f"Could not start CWBridge: {exc}") from exc

    deadline = time.monotonic() + timeout
    send_input = True
    while True:
        if cancel_event is not None and cancel_event.is_set():
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if process.poll() is None:
                    process.kill()
                process.communicate()
            raise CWBridgeCancelled("CWBridge operation was cancelled.")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if process.poll() is None:
                process.kill()
            process.communicate()
            raise CWBridgeError(f"CWBridge timed out after {timeout:g} seconds.")

        try:
            pending_input = request if send_input else None
            send_input = False
            stdout, stderr = process.communicate(input=pending_input, timeout=min(0.25, remaining))
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            continue
