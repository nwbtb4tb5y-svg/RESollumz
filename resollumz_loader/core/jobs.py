import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass


_logger = logging.getLogger("resollumz_loader.jobs")


@dataclass
class JobState:
    busy: bool = False
    message: str = "Release list is not cached. Enable network access and refresh it."
    error: bool = False
    thread: threading.Thread | None = None
    pending: tuple[bool, str] | None = None


state = JobState()
_lock = threading.Lock()


def start(function: Callable[[], str]) -> bool:
    with _lock:
        if state.busy:
            return False
        state.busy = True
        state.error = False
        state.message = "Working..."
        state.pending = None

        def run() -> None:
            try:
                message = function()
            except Exception as exc:
                _logger.exception("Background release operation failed")
                result = False, str(exc)
            else:
                result = True, message
            with _lock:
                state.busy = False
                state.pending = result

        state.thread = threading.Thread(target=run, name="RESollumzReleaseJob", daemon=True)
        state.thread.start()
        return True


def finish_pending(on_success: Callable[[], str] | None = None) -> tuple[bool, str]:
    with _lock:
        pending = state.pending
        state.pending = None
    if pending is None:
        return False, "Background job completed without a result."

    succeeded, message = pending
    if succeeded and on_success is not None:
        try:
            message = f"{message} {on_success()}"
        except Exception as exc:
            _logger.exception("Could not activate the installed Sollumz release")
            succeeded, message = False, str(exc)
    with _lock:
        state.error = not succeeded
        state.message = message
    return succeeded, message
