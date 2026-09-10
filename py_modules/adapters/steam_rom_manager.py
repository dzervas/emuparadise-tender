"""Preflight and launch an EmuDeck SRM job outside the Game Mode session."""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any


class SteamRomManagerAdapter:
    def __init__(self, *, installation: Any, user_home: str, data_dir: str) -> None:
        self._installation = installation
        self._home = Path(user_home)
        self._directory = Path(data_dir) / "srm"
        self._unit = "tender-srm-update.service"

    @property
    def enabled(self) -> bool:
        return self._installation.kind == "emudeck"

    def _account(self):
        return pwd.getpwuid(self._home.stat().st_uid)

    def _user_command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        account = self._account()
        return subprocess.run(
            ["runuser", "-u", account.pw_name, "--", "env", f"XDG_RUNTIME_DIR=/run/user/{account.pw_uid}", *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def busy(self) -> bool:
        result = subprocess.run(
            ["systemctl", "show", self._unit, "--property=ActiveState", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() in ("active", "activating", "deactivating", "reloading")

    def _preflight(self) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("Steam ROM Manager is only used for EmuDeck")
        for executable in ("systemd-run", "runuser", "xvfb-run", "Xvfb", "xauth", "python3", "pgrep"):
            if shutil.which(executable) is None:
                raise ValueError(f"Game Mode SRM requires {executable}; Steam has not been stopped")
        account = self._account()
        if account.pw_uid == 0:
            raise ValueError("SRM must run as the Steam user, not root")
        existing = subprocess.run(
            [
                "pgrep",
                "-u",
                str(account.pw_uid),
                "-f",
                r"(^|/)(steam-rom-manager|Steam ROM Manager|Steam-ROM-Manager)([ .]|$)",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if existing.returncode != 1:
            raise ValueError("Close any existing Steam ROM Manager process before updating")
        root = Path(self._installation.retrodeck_home())
        candidates = [
            root / "tools" / name
            for name in (
                "Steam-ROM-Manager.AppImage",
                "Steam ROM Manager.AppImage",
                "srm/Steam-ROM-Manager.AppImage",
            )
        ]
        srm = next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
        if srm is None:
            raise ValueError("Install Steam ROM Manager through EmuDeck first")
        settings = self._home / ".config/steam-rom-manager/userData/userSettings.json"
        if not settings.is_file():
            raise ValueError("Configure Steam ROM Manager in EmuDeck first")
        json.loads(settings.read_text())
        for session in ("gamescope-session.service", "gamescope-session-plus@steam.service"):
            if self._user_command(["systemctl", "--user", "is-active", "--quiet", session]).returncode == 0:
                break
        else:
            raise ValueError("No supported systemd Game Mode session found; Steam has not been stopped")
        return {"session": session, "srm": str(srm), "xvfb": shutil.which("xvfb-run")}

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {"enabled": self.enabled, "ready": False, "busy": False}
        if not self.enabled:
            return result
        try:
            result["busy"] = self.busy()
            self._preflight()
            result["ready"] = True
        except Exception as exc:
            result["message"] = str(exc)
        with suppress(OSError, ValueError):
            result["job"] = json.loads((self._directory / "status.json").read_text())
        return result

    def start(self) -> dict[str, Any]:
        try:
            job = self._preflight()
            if self.busy():
                raise ValueError("A Steam library update is already running")
            account = self._account()
            self._directory.mkdir(parents=True, exist_ok=True)
            if self._directory.is_symlink():
                raise ValueError("SRM status directory must not be a symlink")
            os.chown(self._directory, account.pw_uid, account.pw_gid, follow_symlinks=False)
            job_path = self._directory / "job.json"
            job_path.unlink(missing_ok=True)
            descriptor = os.open(job_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w") as file:
                os.fchown(file.fileno(), account.pw_uid, account.pw_gid)
                file.write(json.dumps(job))
            worker = Path(__file__).with_name("srm_worker.py")
            for args in (["test", "-r", str(worker)], ["test", "-w", str(self._directory)]):
                if self._user_command(args).returncode:
                    raise ValueError("The Steam user cannot access Tender's SRM worker or status directory")
            subprocess.run(
                [
                    "systemd-run",
                    "--collect",
                    f"--unit={self._unit}",
                    f"--uid={account.pw_uid}",
                    "--property=PAMName=login",
                    "--property=RuntimeMaxSec=20min",
                    "--property=TimeoutStopSec=90",
                    "--property=Type=exec",
                    f"--setenv=HOME={self._home}",
                    f"--setenv=XDG_RUNTIME_DIR=/run/user/{account.pw_uid}",
                    "--setenv=APPIMAGE_EXTRACT_AND_RUN=1",
                    "--working-directory=" + str(self._home),
                    str(shutil.which("python3")),
                    str(worker),
                    str(job_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return {"success": True, "message": "Updating Steam library; Game Mode will restart"}
        except Exception as exc:
            return {"success": False, "reason": "srm_unavailable", "message": str(exc)}
