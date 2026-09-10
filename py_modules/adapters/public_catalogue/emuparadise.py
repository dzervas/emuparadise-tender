"""EmuParadise metadata; download availability belongs to a separate provider."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from models.content_provider import CatalogueEntry

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, checked_url
from adapters.public_catalogue.page import PublicPage


class EmuparadiseCatalogueAdapter:
    page_hosts = frozenset({"www.emuparadise.me", "emuparadise.me"})

    def __init__(self, *, http: PublicHttpAdapter) -> None:
        self._http = http

    def get_entry(self, page_url: str) -> CatalogueEntry:
        page_url = checked_url(page_url, self.page_hosts)
        match = re.fullmatch(r"/([^/]+)/[^/]+/([0-9]+)", urlsplit(page_url).path)
        if not match or urlsplit(page_url).query:
            raise PublicSourceError("Choose an EmuParadise game catalogue page")
        page = PublicPage(self._http.read_html(page_url))
        title = re.sub(r"\s+(?:ROM|ISO)\s*$", "", page.heading.strip())
        if not title or not page.meta.get("og:title"):
            raise PublicSourceError("EmuParadise did not return a game catalogue entry")
        cover = page.meta.get("og:image") or None
        if cover is not None:
            cover = checked_url(cover, frozenset({"r.mprd.se"}))
        return CatalogueEntry(
            provider="emuparadise",
            external_id=match[2],
            page_url=page_url,
            title=title,
            platform=match[1],
            cover_url=cover,
            description=page.meta.get("og:description", ""),
        )
