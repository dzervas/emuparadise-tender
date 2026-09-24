import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

plugin_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(plugin_dir, "py_modules"))
import decky
from bootstrap import bootstrap

from adapters.public_catalogue.http import _system_ssl_context, checked_url
from adapters.public_catalogue.release import download_latest_release
from lib.installation_gate import installation_restart_blocked, srm_update_blocked


class Plugin:
    _installation_restart_required = False
    _srm_mutations = 0
    _eden_cached_process: tuple[int, list[str]] | None = None

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self._runtime = bootstrap(
            user_home=decky.DECKY_USER_HOME, plugin_dir=decky.DECKY_PLUGIN_DIR, emit=decky.emit, logger=decky.logger
        )
        self.settings = self._runtime.settings
        self._download_service = self._runtime.downloads
        self._catalogue_service = self._runtime.search
        self._rom_removal_service = self._runtime.removal
        self._srm = self._runtime.srm
        self._active_selection = self.settings.get("emulator_installation", "auto")
        self._artwork_slots = asyncio.Semaphore(4)
        self._artwork_cache = {}
        self._release_lock = asyncio.Lock()
        self._download_service.cleanup_leftover_tmp_files()
        decky.logger.info("Tender public catalogue ready")

    async def _unload(self):
        await self._download_service.shutdown()

    async def log_error(self, message):
        decky.logger.error(message)

    async def log_info(self, message):
        decky.logger.info(message)

    async def get_emulator_installation(self):
        return {
            "success": True,
            "selection": self.settings.get("emulator_installation", "auto"),
            "active_selection": self._active_selection,
            "restart_required": self._installation_restart_required,
        }

    @srm_update_blocked
    async def save_emulator_installation(self, selection):
        if selection not in {"auto", "retrodeck", "emudeck"}:
            return {"success": False, "message": "Unknown emulator installation"}
        if any(
            item["status"] not in ("completed", "failed", "cancelled")
            for item in self._download_service.get_download_queue()["downloads"]
        ):
            return {"success": False, "message": "Finish or cancel downloads first"}
        self.settings["emulator_installation"] = selection
        try:
            await self.loop.run_in_executor(None, self._runtime.persistence.save_settings, self.settings)
        except Exception:
            decky.logger.exception("Could not save installation")
            raise
        self._installation_restart_required = selection != self._active_selection
        return {"success": True, "restart_required": self._installation_restart_required}

    @installation_restart_blocked
    @srm_update_blocked
    async def start_download(
        self, rom_id, replace_existing=False, candidate_path=None, collision_choice=None, page_saw_candidate=False
    ):
        return await self._download_service.start_download(
            rom_id, replace_existing, candidate_path, collision_choice, page_saw_candidate
        )

    @installation_restart_blocked
    @srm_update_blocked
    async def resume_download(self, rom_id):
        return await self._download_service.resume_download(rom_id)

    @srm_update_blocked
    async def remove_rom(self, rom_id):
        if self._runtime.api.get_rom(rom_id) is None:
            return {"success": False, "message": "Unknown catalogue item"}
        return await self._rom_removal_service.remove_rom(rom_id)

    async def get_catalogue_artwork(self, catalogue_url):
        async with self._artwork_slots:
            if catalogue_url not in self._artwork_cache:
                try:
                    entry = await self.loop.run_in_executor(None, self._runtime.ep.get_entry, catalogue_url)
                    if len(self._artwork_cache) >= 512:
                        self._artwork_cache.pop(next(iter(self._artwork_cache)))
                    self._artwork_cache[catalogue_url] = entry.cover_url
                except Exception:
                    decky.logger.exception("Catalogue artwork unavailable")
                    return {"cover_url": None}
            return {"cover_url": self._artwork_cache[catalogue_url]}

    async def fetch_cover_base64(self, rom_id):
        import urllib.request

        def fetch():
            cover = self._runtime.api.get_rom(rom_id).get("url_cover")
            if not cover:
                return {"base64": None}
            cover = checked_url(cover, frozenset({"r.mprd.se"}))
            from adapters.public_catalogue.http import _SourceRedirects

            opener = urllib.request.build_opener(
                _SourceRedirects(frozenset({"r.mprd.se"})), urllib.request.HTTPSHandler(context=_system_ssl_context())
            )
            with opener.open(cover, timeout=30) as response:
                data = response.read(8_000_001)
                if len(data) > 8_000_000 or not response.headers.get_content_type().startswith("image/"):
                    raise ValueError("Invalid cover image")
            return {"base64": base64.b64encode(data).decode()}

        return await self.loop.run_in_executor(None, fetch)

    async def download_latest_release(self):
        if self._release_lock.locked():
            return {"success": False, "message": "A release download is already running"}
        async with self._release_lock:
            try:
                return await self.loop.run_in_executor(None, download_latest_release, decky.DECKY_USER_HOME)
            except Exception as exc:
                decky.logger.exception("Tender release download failed")
                return {"success": False, "message": str(exc)}

    async def cancel_download(self, rom_id):
        return self._download_service.cancel_download(rom_id)

    async def pause_download(self, rom_id):
        return self._download_service.pause_download(rom_id)

    async def get_download_queue(self):
        return self._download_service.get_download_queue()

    async def clear_completed_downloads(self):
        return self._download_service.clear_completed_downloads()

    async def get_installed_rom(self, rom_id):
        return self._download_service.get_installed_rom(rom_id)

    async def inspect_catalogue_entry(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        return await self._catalogue_service.inspect(catalogue_url, provider, download_url)

    @installation_restart_blocked
    @srm_update_blocked
    async def import_catalogue_entry(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        rom_id = await self._catalogue_service.bound_rom_id(catalogue_url)
        queue = self._download_service.get_download_queue()["downloads"]
        if (
            self._srm_mutations > 1
            or rom_id in self._download_service.active_download_rom_ids()
            or any(
                item["rom_id"] == rom_id and item["status"] not in ("completed", "failed", "cancelled")
                for item in queue
            )
        ):
            return {
                "success": False,
                "reason": "downloads_active",
                "message": "Finish or cancel this game's download before changing its source",
            }
        self._catalogue_import_in_progress = True
        try:
            return await self._catalogue_service.import_entry(catalogue_url, provider, download_url)
        finally:
            self._catalogue_import_in_progress = False

    async def bind_catalogue_shortcut(self, rom_id: int, app_id: int) -> dict[str, Any]:
        return await self._catalogue_service.bind_shortcut(rom_id, app_id)

    async def list_catalogue_entries(self) -> dict[str, Any]:
        return await self._catalogue_service.list_entries()

    async def get_srm_status(self) -> dict[str, Any]:
        return await asyncio.get_running_loop().run_in_executor(None, self._srm.status)

    @installation_restart_blocked
    @srm_update_blocked
    async def update_srm_library(self) -> dict[str, Any]:
        if getattr(self, "_srm_mutations", 0) > 1:
            return {
                "success": False,
                "reason": "operations_active",
                "message": "Wait for ongoing imports or file operations to finish",
            }
        queue = self._download_service.get_download_queue()["downloads"]
        if self._download_service.active_download_rom_ids() or any(
            item["status"] not in ("completed", "failed", "cancelled") for item in queue
        ):
            return {"success": False, "reason": "downloads_active", "message": "Finish or cancel downloads first"}
        self._srm_starting = True
        try:
            if await self._catalogue_service.has_bound_shortcuts():
                return {
                    "success": False,
                    "reason": "shortcuts_owned",
                    "message": "Remove existing Tender-managed shortcuts before handing this library to SRM",
                }
            return await asyncio.get_running_loop().run_in_executor(None, self._srm.start)
        finally:
            self._srm_starting = False

    async def search_catalogue(self, query: str, platform: str = "any") -> dict[str, Any]:
        return await self._catalogue_service.search(query, platform)

    async def get_catalogue_downloads(self, catalogue_url: str) -> dict[str, Any]:
        return await self._catalogue_service.downloads_for(catalogue_url)

    @classmethod
    def _eden_process(cls) -> tuple[int, list[str]] | None:
        """Return the running Eden process, caching it until that PID exits."""

        cached = cls._eden_cached_process
        if cached is not None and Path(f"/proc/{cached[0]}").exists():
            return cached

        cls._eden_cached_process = None
        candidates: list[tuple[int, list[str]]] = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                raw = (proc / "cmdline").read_bytes()
                if not raw:
                    continue
                argv = [part.decode(errors="replace") for part in raw.rstrip(b"\0").split(b"\0")]
                command = os.path.basename(argv[0]).lower()
                try:
                    executable = os.path.basename(os.readlink(proc / "exe")).lower()
                except OSError:
                    executable = ""
            except (OSError, PermissionError):
                continue

            if (
                command in {"eden", "eden-cli"}
                or command.startswith("eden-")
                or "eden.appimage" in command
                or executable in {"eden", "eden-cli"}
                or executable.startswith("eden-")
            ):
                candidates.append((int(proc.name), argv))

        if not candidates:
            return None

        chosen = next((candidate for candidate in candidates if cls._eden_rom_from_argv(candidate[1])), candidates[0])
        cls._eden_cached_process = chosen
        return chosen

    @staticmethod
    def _eden_rom_from_argv(argv: list[str]) -> str | None:
        extensions = {".xci", ".nsp", ".nca", ".nro", ".nso"}
        for index, arg in enumerate(argv[:-1]):
            if arg in {"-g", "--game"}:
                candidate = argv[index + 1]
                if Path(candidate).suffix.lower() in extensions:
                    return candidate
        for arg in reversed(argv[1:]):
            if Path(arg).suffix.lower() in extensions:
                return arg
        return None

    @staticmethod
    def _normalise_switch_title(value: str) -> str:
        value = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", value)
        value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
        return " ".join(value.split())

    @classmethod
    def _eden_title_id(cls, rom_path: str | None) -> int | None:
        if not rom_path:
            return None
        match = re.search(r"(?i)(?:^|[^0-9a-f])(01[0-9a-f]{14})(?:[^0-9a-f]|$)", Path(rom_path).stem)
        return int(match.group(1), 16) if match else None

    @classmethod
    def _eden_lobbies_for_game(cls, rom_path: str | None) -> tuple[list[dict[str, Any]], int]:
        if not rom_path:
            return [], 0

        request = urllib.request.Request(
            "https://api.ynet-fun.xyz/lobby",
            headers={"User-Agent": "Tender/0.33 Eden lobby checker"},
        )
        with urllib.request.urlopen(request, timeout=5, context=_system_ssl_context()) as response:
            payload = json.load(response)

        rooms = payload.get("rooms", [])
        if not isinstance(rooms, list):
            return [], 0

        title_id = cls._eden_title_id(rom_path)
        rom_name = cls._normalise_switch_title(Path(rom_path).stem)
        matched: list[dict[str, Any]] = []

        for room in rooms:
            if not isinstance(room, dict):
                continue
            preferred_id = room.get("preferredGameId")
            preferred_name = cls._normalise_switch_title(str(room.get("preferredGameName", "")))

            id_matches = title_id is not None and preferred_id == title_id
            name_matches = bool(
                rom_name
                and preferred_name
                and preferred_name not in {"any", "any game", "all games", "all games welcome", "switch games"}
                and (preferred_name in rom_name or rom_name in preferred_name)
            )
            players = len(room.get("players", [])) if isinstance(room.get("players"), list) else 0
            if (id_matches or name_matches) and players > 0:
                matched.append(
                    {
                        "name": str(room.get("name", "Unnamed room")),
                        "players": players,
                        "max_players": room.get("maxPlayers"),
                        "has_password": bool(room.get("hasPassword", False)),
                    }
                )

        return matched, len(rooms)

    @staticmethod
    def _eden_environment(pid: int) -> dict[str, str]:
        """Build an xdotool environment from the running Eden process."""

        env = os.environ.copy()
        try:
            raw = Path(f"/proc/{pid}/environ").read_bytes()
            for item in raw.split(b"\0"):
                if b"=" not in item:
                    continue
                key, value = item.split(b"=", 1)
                name = key.decode(errors="replace")
                if name in {"DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR"}:
                    env[name] = value.decode(errors="replace")
        except (OSError, PermissionError):
            pass
        return env

    async def send_eden_hotkey(self, key: str) -> dict[str, Any]:
        allowed = {"b", "c", "l", "n", "r", "comma", "period"}
        if key not in allowed:
            return {"success": False, "message": "Unsupported Eden hotkey"}

        process = await self.loop.run_in_executor(None, self._eden_process)
        if process is None:
            return {"success": False, "message": "Eden is not running"}

        pid, _ = process
        env = self._eden_environment(pid)

        def send() -> dict[str, Any]:
            try:
                result = subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", f"ctrl+{key}"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
            except FileNotFoundError:
                return {"success": False, "message": "xdotool is not installed"}
            except subprocess.TimeoutExpired:
                return {"success": False, "message": "xdotool timed out"}

            if result.returncode != 0:
                message = (result.stderr or result.stdout or "xdotool failed").strip()
                return {"success": False, "message": message}
            return {"success": True, "message": ""}

        return await self.loop.run_in_executor(None, send)

    async def get_eden_status(self) -> dict[str, Any]:
        process = await self.loop.run_in_executor(None, self._eden_process)
        if process is None:
            return {
                "running": False,
                "game_name": None,
                "rom_path": None,
                "title_id": None,
                "lobby_count": 0,
                "lobbies": [],
                "total_lobbies": 0,
            }

        pid, argv = process
        rom_path = self._eden_rom_from_argv(argv)
        game_name = Path(rom_path).stem if rom_path else None
        title_id = self._eden_title_id(rom_path)
        try:
            lobbies, total = await self.loop.run_in_executor(None, self._eden_lobbies_for_game, rom_path)
            lobby_error = None
        except Exception as exc:
            decky.logger.warning("Could not query Eden public lobbies: %s", exc)
            lobbies, total = [], 0
            lobby_error = str(exc)

        return {
            "running": True,
            "pid": pid,
            "game_name": game_name,
            "rom_path": rom_path,
            "title_id": f"{title_id:016X}" if title_id is not None else None,
            "lobby_count": len(lobbies),
            "lobbies": lobbies,
            "total_lobbies": total,
            "lobby_error": lobby_error,
        }


