"""Compatibility boundary preserving RomM extensions without leaking public IDs."""

from __future__ import annotations

import inspect
from typing import Any

from models.cover import CoverRevalidation

from adapters.public_catalogue.http import PublicSourceError
from domain.provider_identity import PUBLIC_ID_START, is_public_id


def _contains_public_id(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "rom_id" and isinstance(item, int) and item >= PUBLIC_ID_START) or _contains_public_id(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_public_id(item) for item in value)
    return False


class ContentApiRouter:
    def __init__(self, *, romm: Any, sources: Any, resolvers: dict[str, Any], transports: dict[str, Any]) -> None:
        self._romm = romm
        self._sources = sources
        self._resolvers = resolvers
        self._transports = transports

    def get_rom(self, rom_id: int) -> dict[str, Any]:
        if is_public_id(rom_id):
            source = self._sources.get(rom_id)
            if source is None:
                raise PublicSourceError("This catalogue item is no longer registered locally")
            return source["detail"]
        return self._romm.get_rom(rom_id)

    def get_rom_once(self, rom_id: int) -> dict[str, Any]:
        if is_public_id(rom_id):
            return self.get_rom(rom_id)
        return self._romm.get_rom_once(rom_id)

    def download_rom_content(self, rom_id, filename, dest, progress_callback=None, *, resume=False, on_meta=None):
        if not is_public_id(rom_id):
            return self._romm.download_rom_content(
                rom_id,
                filename,
                dest,
                progress_callback,
                resume=resume,
                on_meta=on_meta,
            )
        source = self._sources.get(rom_id)
        if source is None:
            raise PublicSourceError("This catalogue item is no longer registered locally")
        provider = source["download_provider"]
        plan = self._resolvers[provider].resolve(source["download_page"])
        if plan.filename != source["detail"]["fs_name"]:
            raise PublicSourceError("The source filename changed; review the download source before installing")
        return self._transports[provider].download_zip(
            plan.file_url,
            dest,
            progress_callback,
            resume=resume,
            on_meta=on_meta,
        )

    def download_cover(self, cover_url, dest, *, etag=None, last_modified=None):
        if cover_url.startswith("https://r.mprd.se/"):
            self._romm.download_cover_from_url(cover_url, dest)
            return CoverRevalidation(not_modified=False, etag=None, last_modified=None)
        return self._romm.download_cover(cover_url, dest, etag=etag, last_modified=last_modified)

    def __getattr__(self, name: str) -> Any:
        method = getattr(self._romm, name)
        if not callable(method):
            return method

        def romm_extension(*args, **kwargs):
            arguments = inspect.signature(method).bind(*args, **kwargs).arguments
            if _contains_public_id(arguments):
                raise PublicSourceError("This catalogue does not support RomM server operations")
            result: Any = method(*args, **kwargs)
            if name.startswith(("list_roms", "list_collection_roms")) and any(
                item.get("id", 0) >= PUBLIC_ID_START for item in result.get("items", [])
            ):
                raise PublicSourceError("The server returned an ID reserved for local catalogue entries")
            return result

        return romm_extension
