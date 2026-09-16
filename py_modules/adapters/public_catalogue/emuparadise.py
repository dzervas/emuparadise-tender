"""EmuParadise metadata; download availability belongs to a separate provider."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlencode, urljoin, urlsplit

from models.content_provider import CatalogueEntry

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, checked_url
from adapters.public_catalogue.page import PublicPage
from domain.catalogue_matching import title_key
from domain.catalogue_platforms import PLATFORMS


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

    def search(self, query: str, platform: str = "any") -> list[CatalogueEntry]:
        query = query.strip()
        if not 2 <= len(query) <= 100:
            raise PublicSourceError("Search with 2-100 characters")
        system = "psx" if platform == "ps1" else platform
        allowed = {row[0] for row in PLATFORMS if platform == "any" or row[2] == system}
        if platform not in {"any", "ps1", "switch", "ps3"} | {row[2] for row in PLATFORMS}:
            raise PublicSourceError("Unknown platform")
        # These systems have no EmuParadise catalogue; never return another platform.
        if not allowed:
            return []
        url = "https://www.emuparadise.me/roms/search.php?" + urlencode(
            {
                "query": query,
                "section": "roms",
                "sysid": {"psx": 2, "ps2": 41, "psp": 44, "gc": 42, "wii": 68, "gb": 12, "gbc": 11, "gba": 31}.get(
                    system, 0
                ),
            }
        )
        page = PublicPage(self._http.read_html(url))
        results = {}
        for link in page.links:
            if not link.get("data-filter"):
                continue
            try:
                target = checked_url(urljoin(url, link.get("href", "")), self.page_hosts)
            except ValueError:
                continue
            match = re.fullmatch(r"/([^/]+)/[^/]+/([0-9]+)", unquote(urlsplit(target).path))
            if not match or match[1] not in allowed or urlsplit(target).query:
                continue
            title = re.sub(r"\s+(?:ROM|ISO)\s*$", "", link["text"].strip())
            if title:
                results.setdefault(
                    match[2],
                    CatalogueEntry("emuparadise", match[2], target, title, match[1], link.get("image") or None),
                )
        return sorted(results.values(), key=lambda item: (title_key(item.title) != title_key(query),))
