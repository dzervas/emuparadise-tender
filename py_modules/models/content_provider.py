"""Source identities and public download plans independent of local ROM IDs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogueEntry:
    provider: str
    external_id: str
    page_url: str
    title: str
    platform: str
    cover_url: str | None = None
    description: str = ""


@dataclass(frozen=True)
class DownloadPlan:
    provider: str
    page_url: str
    file_url: str
    filename: str
    archive: str = "zip"
    size: str | None = None
    region: str | None = None
