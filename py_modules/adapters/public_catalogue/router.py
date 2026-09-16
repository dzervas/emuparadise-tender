"""Locally registered public catalogue content."""

from adapters.public_catalogue.http import PublicSourceError


class ContentApiRouter:
    def __init__(self, *, sources, resolvers, transports):
        self._sources = sources
        self._resolvers = resolvers
        self._transports = transports

    def get_rom(self, rom_id):
        source = self._sources.get(rom_id)
        if source is None:
            raise PublicSourceError("Unknown local catalogue item")
        return source["detail"]

    def get_rom_once(self, rom_id):
        return self.get_rom(rom_id)

    def download_rom_content(self, rom_id, _filename, dest, progress_callback=None, *, resume=False, on_meta=None):
        source = self._sources.get(rom_id)
        if source is None:
            raise PublicSourceError("This catalogue item is no longer registered locally")
        provider = source["download_provider"]
        plan = self._resolvers[provider].resolve(source["download_page"])
        if plan.filename != source["detail"]["fs_name"]:
            raise PublicSourceError("The source filename changed; review the download source before installing")
        headers = {"referer": plan.page_url} if provider == "vimm" else {}
        return self._transports[provider].download_zip(
            plan.file_url,
            dest,
            progress_callback,
            resume=resume,
            on_meta=on_meta,
            **headers,
        )
