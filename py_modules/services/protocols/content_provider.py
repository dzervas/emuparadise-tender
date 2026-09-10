"""Independent public catalogue and download-resolution contracts."""

from typing import Any, Protocol

from models.content_provider import CatalogueEntry, DownloadPlan


class CatalogueReader(Protocol):
    def get_entry(self, page_url: str) -> CatalogueEntry: ...


class DownloadResolverReader(Protocol):
    def resolve(self, page_url: str) -> DownloadPlan: ...


class CatalogueSourceStore(Protocol):
    def get(self, rom_id: int) -> dict[str, Any] | None: ...

    def register(self, catalogue: str, external_id: str, detail: dict[str, Any], provider: str, page: str) -> int: ...
