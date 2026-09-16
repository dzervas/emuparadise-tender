import asyncio
import base64
import os
import sys
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
