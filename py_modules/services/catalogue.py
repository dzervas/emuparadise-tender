"""On-demand catalogue imports into Tender's existing ROM and shortcut model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from domain.catalogue_platforms import catalogue_system
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
        SystemResolver,
        UnitOfWorkFactory,
    )


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


class CatalogueService:
    def __init__(self, *, config: CatalogueServiceConfig) -> None:
        self._config = config

    async def inspect(self, catalogue_url: str, provider: str, download_url: str) -> dict[str, Any]:
        try:
            return await self._config.loop.run_in_executor(
                None, self._inspect_io, catalogue_url, provider, download_url
            )
        except Exception as exc:
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
        return {"success": True, "rom_id": rom_id, "app_id": app_id, "shortcut": shortcut}

    async def bind_shortcut(self, rom_id: int, app_id: int) -> dict[str, Any]:
        try:
            await self._config.loop.run_in_executor(None, self._bind_io, rom_id, app_id)
            return {"success": True}
        except Exception as exc:
            return {"success": False, "reason": "shortcut_bind_failed", "message": str(exc)}

    def _bind_io(self, rom_id: int, app_id: int) -> None:
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
