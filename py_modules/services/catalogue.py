"""On-demand catalogue imports into Tender's existing ROM and shortcut model."""

from __future__ import annotations

import logging
from asyncio import gather
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from domain.catalogue_platforms import PLATFORMS, catalogue_system
from domain.rom import Rom
from domain.rom_metadata_mapping import build_rom_metadata
from domain.shortcut_data import build_shortcuts_data

if TYPE_CHECKING:
    import asyncio

    from services.protocols import (
        CatalogueReader,
        CatalogueSourceStore,
        Clock,
        DownloadResolverReader,
        RomDetailReader,
        SystemResolver,
        UnitOfWorkFactory,
    )


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogueServiceConfig:
    catalogue: CatalogueReader
    resolve_system: SystemResolver
    sources: CatalogueSourceStore
    resolvers: dict[str, DownloadResolverReader]
    uow_factory: UnitOfWorkFactory
    clock: Clock
    loop: asyncio.AbstractEventLoop
    plugin_dir: str
    shortcut_owner: str = "tender"
    romm: RomDetailReader | None = None


class CatalogueService:
    def __init__(self, *, config: CatalogueServiceConfig) -> None:
        self._config = config

    async def inspect(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        try:
            return await self._config.loop.run_in_executor(
                None, self._inspect_io, catalogue_url, provider, download_url
            )
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "source_unavailable", "message": str(exc)}

    def _inspect_io(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        if provider not in self._config.resolvers:
            raise ValueError("Choose Romspedia or RomsDL")
        entry = self._config.catalogue.get_entry(catalogue_url)
        plan = self._config.resolvers[provider].resolve(download_url)
        download_section = plan.page_url.split("/")[4]
        system = catalogue_system(entry.platform, download_section)
        return {"success": True, "entry": asdict(entry), "download": asdict(plan), "system": system}

    async def import_entry(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        try:
            return await self._config.loop.run_in_executor(None, self._import_io, catalogue_url, provider, download_url)
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "import_failed", "message": str(exc)}

    def _import_io(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        inspected = self._inspect_io(catalogue_url, provider, download_url)
        entry, plan, system = inspected["entry"], inspected["download"], inspected["system"]
        system = self._config.resolve_system(system, system)
        detail = {
            "name": entry["title"],
            "fs_name": plan["filename"],
            "platform_slug": system,
            "platform_fs_slug": system,
            "platform_name": entry["platform"].replace("_", " "),
            "fs_size_bytes": 0,
            "has_multiple_files": True,
            "files": [],
            "url_cover": entry["cover_url"],
            "path_cover_large": entry["cover_url"],
            "summary": entry["description"],
            "igdb_metadata": {"summary": entry["description"]},
        }
        rom_id = self._config.sources.register("emuparadise", entry["external_id"], detail, provider, plan["page_url"])
        source = self._config.sources.get(rom_id)
        if source is None:
            raise ValueError("The catalogue identity could not be retained")
        detail = source["detail"]
        with self._config.uow_factory() as uow:
            rom = uow.roms.get(rom_id)
            if rom is None:
                rom = Rom.synced(
                    rom_id=rom_id,
                    platform_slug=detail["platform_slug"],
                    name=detail["name"],
                    fs_name=detail["fs_name"],
                    shortcut_app_id=None,
                    synced_at=self._config.clock.now().isoformat(),
                )
                uow.roms.save(rom)
                uow.rom_metadata.save(rom_id, build_rom_metadata(detail, self._config.clock.time()))
            app_id = rom.shortcut_app_id
        shortcut = build_shortcuts_data([detail], self._config.plugin_dir, {}, {})[0]
        return {
            "success": True,
            "rom_id": rom_id,
            "app_id": app_id,
            "shortcut": shortcut,
            "shortcut_owner": self._config.shortcut_owner,
        }

    async def bind_shortcut(self, rom_id: int, app_id: int) -> dict[str, Any]:
        try:
            await self._config.loop.run_in_executor(None, self._bind_io, rom_id, app_id)
            return {"success": True}
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "shortcut_bind_failed", "message": str(exc)}

    def _bind_io(self, rom_id: int, app_id: int) -> None:
        if self._config.shortcut_owner == "srm":
            raise ValueError("Steam ROM Manager owns EmuDeck shortcuts")
        if self._config.sources.get(rom_id) is None:
            raise ValueError("Unknown catalogue item")
        with self._config.uow_factory() as uow:
            rom = uow.roms.get(rom_id)
            if rom is None:
                raise ValueError("Import the catalogue item first")
            if rom.shortcut_app_id is not None and rom.shortcut_app_id != app_id:
                raise ValueError("This catalogue item already has a Steam shortcut")
            owner = uow.roms.get_by_app_id(app_id)
            if owner is not None and owner.rom_id != rom_id:
                raise ValueError("This Steam shortcut already belongs to another catalogue item")
            rom.bind_shortcut(app_id)
            uow.roms.save(rom)

    async def list_entries(self) -> dict[str, Any]:
        return await self._config.loop.run_in_executor(None, self._list_io)

    def _list_io(self) -> dict[str, Any]:
        with self._config.uow_factory() as uow:
            return {
                "success": True,
                "items": [
                    {"rom_id": rom.rom_id, "name": rom.name, "installed": uow.rom_installs.get(rom.rom_id) is not None}
                    for rom in uow.roms.iter_all()
                ],
            }

    async def import_romm(self, rom_id: int) -> dict[str, Any]:
        try:
            return await self._config.loop.run_in_executor(None, self._import_romm_io, rom_id)
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "import_failed", "message": str(exc)}

    def _import_romm_io(self, rom_id: int) -> dict[str, Any]:
        from domain.provider_identity import is_public_id

        if self._config.shortcut_owner != "srm" or self._config.romm is None:
            raise ValueError("Use RomM library sync for RetroDECK")
        if rom_id <= 0 or is_public_id(rom_id):
            raise ValueError("Enter a valid RomM ROM ID")
        detail = self._config.romm.get_rom(rom_id)
        system = self._config.resolve_system(detail["platform_slug"], detail.get("platform_fs_slug"))
        with self._config.uow_factory() as uow:
            if uow.roms.get(rom_id) is None:
                uow.roms.save(
                    Rom.synced(
                        rom_id=rom_id,
                        platform_slug=system,
                        name=detail["name"],
                        fs_name=detail["fs_name"],
                        shortcut_app_id=None,
                        synced_at=self._config.clock.now().isoformat(),
                    )
                )
                uow.rom_metadata.save(rom_id, build_rom_metadata(detail, self._config.clock.time()))
        return {"success": True, "rom_id": rom_id}

    async def has_bound_shortcuts(self) -> bool:
        return await self._config.loop.run_in_executor(None, self._has_bound_io)

    def _has_bound_io(self) -> bool:
        with self._config.uow_factory() as uow:
            return any(rom.shortcut_app_id is not None for rom in uow.roms.iter_all())

    async def search(self, query: str) -> dict[str, Any]:
        try:
            entries = await self._config.loop.run_in_executor(None, self._config.catalogue.search, query)
            return {"success": True, "items": [asdict(entry) for entry in entries[:5]]}
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "search_failed", "message": str(exc), "items": []}

    async def downloads_for(self, catalogue_url: str) -> dict[str, Any]:
        try:
            entry = await self._config.loop.run_in_executor(None, self._config.catalogue.get_entry, catalogue_url)
            platform = next(row[1] for row in PLATFORMS if row[0] == entry.platform)
            providers = list(self._config.resolvers.items())
            for provider, _ in providers:
                _logger.info("Searching download provider %s: title=%r platform=%s", provider, entry.title, platform)
            answers = await gather(
                *[
                    self._config.loop.run_in_executor(None, resolver.search, entry.title, platform)
                    for _, resolver in providers
                ],
                return_exceptions=True,
            )
            items, messages, provider_results = [], [], []
            for (provider, _), answer in zip(providers, answers, strict=True):
                if isinstance(answer, BaseException):
                    _logger.error(
                        "%s download search failed", provider, exc_info=(type(answer), answer, answer.__traceback__)
                    )
                    message = str(answer)
                    messages.append(f"{provider}: search unavailable ({message})")
                    provider_results.append({"provider": provider, "success": False, "count": 0, "message": message})
                else:
                    items.extend(asdict(plan) for plan in answer)
                    message = f"{len(answer)} download option(s)" if answer else "No matching published downloads"
                    _logger.info("Download provider %s: %s", provider, message)
                    provider_results.append(
                        {"provider": provider, "success": True, "count": len(answer), "message": message}
                    )
            return {
                "success": True,
                "entry": asdict(entry),
                "items": items,
                "messages": messages,
                "provider_results": provider_results,
            }
        except Exception as exc:
            _logger.exception("Catalogue operation failed")
            return {"success": False, "reason": "source_unavailable", "message": str(exc), "items": []}
