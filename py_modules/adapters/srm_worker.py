"""Detached SRM job: the session stays stopped until the library write finishes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any


def write_status(path: Path, status: str, message: str) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"status": status, "message": message}))
    temporary.replace(path)


def command(args: list[str], *, timeout: int = 60, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(args, check=True, timeout=timeout, **kwargs)


def run_job(job: dict[str, Any], status_path: Path) -> None:
    session = job["session"]
    restart_needed = False
    failure = None
    try:
        write_status(status_path, "running", "Stopping Game Mode to update the Steam library")
        restart_needed = True
        command(["systemctl", "--user", "stop", session])
        probe = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "steam"], check=False)
        if probe.returncode != 1:
            raise RuntimeError("Steam is still running; no SRM write was attempted")
        write_status(status_path, "running", "Steam ROM Manager is updating all enabled parsers")
        with status_path.with_suffix(".log").open("w") as log:
            process = subprocess.Popen(
                [job["xvfb"], "-a", job["srm"], "add"],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=900)
                if code:
                    raise RuntimeError(f"Steam ROM Manager exited with code {code}; see status.log")
            finally:
                # Electron/Xvfb children must not keep writing after Steam returns.
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()

        write_status(status_path, "running", "SRM finished; returning to Game Mode")
    except Exception as exc:
        failure = str(exc)
    finally:
        if restart_needed:
            try:
                command(["systemctl", "--user", "start", session])
            except Exception as exc:
                failure = f"{failure or 'SRM finished'}. Game Mode restart failed: {exc}"
        write_status(
            status_path,
            "failed" if failure else "completed",
            failure or "SRM finished. Check your Steam library; parser exclusions and unmatched games still apply.",
        )


def interrupted(_signum, _frame):
    raise RuntimeError("SRM worker was interrupted; attempting to restore Game Mode")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    job_path = Path(sys.argv[1])
    run_job(json.loads(job_path.read_text()), job_path.with_name("status.json"))
