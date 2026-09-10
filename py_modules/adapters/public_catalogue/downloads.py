"""Published Romspedia and RomsDL download flows, independent of the catalogue."""

from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlsplit

from models.content_provider import DownloadPlan

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, checked_url
from adapters.public_catalogue.page import PublicPage


def _game_page(url: str, hosts: frozenset[str]) -> str:
    url = checked_url(url, hosts)
    if not re.fullmatch(r"/roms/[^/]+/[^/]+", urlsplit(url).path) or urlsplit(url).query:
        raise PublicSourceError("Choose a game page on the selected download provider")
    return url


def _zip_plan(provider: str, page_url: str, urls: list[str], host: str) -> DownloadPlan:
    candidates = set()
    for url in urls:
        if urlsplit(url).hostname == host:
            candidates.add(checked_url(url, frozenset({host})))
    if len(candidates) != 1:
        raise PublicSourceError("The source did not publish one unambiguous download link")
    file_url = candidates.pop()
    filename = unquote(urlsplit(file_url).path.rsplit("/", 1)[-1])
    if (
        not filename.lower().endswith(".zip")
        or "/" in filename
        or "\\" in filename
        or any(ord(c) < 32 for c in filename)
        or filename in (".zip", "..zip")
    ):
        raise PublicSourceError("The source did not publish a supported ZIP filename")
    return DownloadPlan(provider=provider, page_url=page_url, file_url=file_url, filename=filename)


class RomspediaDownloadAdapter:
    """Resolve only the game page's published slow-download link and file link."""

    page_hosts = frozenset({"www.romspedia.com", "romspedia.com"})
    file_host = "downloads.romspedia.com"

    def __init__(self, *, http: PublicHttpAdapter) -> None:
        self._http = http

    def resolve(self, page_url: str) -> DownloadPlan:
        page_url = _game_page(page_url, self.page_hosts)
        page = PublicPage(self._http.read_html(page_url))
        links = {
            urljoin(page_url, link["href"])
            for link in page.links
            if link.get("id") == "btnDownload_slow" and link.get("href")
        }
        if len(links) != 1:
            raise PublicSourceError("Romspedia's public download link is unavailable")
        landing_url = checked_url(links.pop(), self.page_hosts)
        if urlsplit(landing_url).path != urlsplit(page_url).path + "/download":
            raise PublicSourceError("Romspedia returned an unexpected download page")
        landing = PublicPage(self._http.read_html(landing_url))
        return _zip_plan(
            "romspedia",
            page_url,
            [urljoin(landing_url, link["href"]) for link in landing.links if link.get("href")],
            self.file_host,
        )


class RomsdlDownloadAdapter:
    """Submit the visible download form and read its literal countdown target."""

    page_hosts = frozenset({"romsdl.com", "www.romsdl.com"})
    file_host = "downloads.retrostic.com"

    def __init__(self, *, http: PublicHttpAdapter) -> None:
        self._http = http

    def resolve(self, page_url: str) -> DownloadPlan:
        page_url = _game_page(page_url, self.page_hosts)
        page = PublicPage(self._http.read_html(page_url))
        forms = [(attrs, fields) for attrs, fields in page.forms if attrs.get("id") == "dl"]
        if len(forms) != 1:
            raise PublicSourceError("RomsDL's public download form is unavailable")
        attrs, fields = forms[0]
        landing_url = checked_url(urljoin(page_url, attrs.get("action", "")), self.page_hosts)
        platform, game = urlsplit(page_url).path.split("/")[-2:]
        if (
            attrs.get("method", "").lower() != "post"
            or urlsplit(landing_url).path != urlsplit(page_url).path + "/download"
            or fields.get("rom_url") != game
            or fields.get("console_url") != platform
            or not fields.get("session")
            or set(fields) != {"rom_url", "console_url", "session"}
        ):
            raise PublicSourceError("RomsDL's public download form has changed")
        landing = PublicPage(self._http.read_html(landing_url, fields=fields))
        # RomsDL publishes this literal inside its visible countdown. Never eval JS.
        targets = [
            match[1]
            for script in landing.scripts
            for match in re.findall(r"""window\.location\.href\s*=\s*(["'])(https://[^"'\\\r\n]+)\1\s*;""", script)
        ]
        return _zip_plan("romsdl", page_url, targets, self.file_host)
