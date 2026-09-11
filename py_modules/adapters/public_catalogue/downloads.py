"""Published Romspedia and RomsDL download flows, independent of the catalogue."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

from models.content_provider import DownloadPlan

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, checked_url
from adapters.public_catalogue.page import PublicPage
from adapters.seven_zip import ensure_7z_available
from domain.catalogue_matching import base_title, download_region, title_key

_logger = logging.getLogger(__name__)


def _game_page(url: str, hosts: frozenset[str]) -> str:
    url = checked_url(url, hosts)
    if not re.fullmatch(r"/roms/[^/]+/[^/]+", urlsplit(url).path) or urlsplit(url).query:
        raise PublicSourceError("Choose a game page on the selected download provider")
    return url


def _archive_plan(provider: str, page_url: str, urls: list[str], host: str) -> DownloadPlan:
    candidates = set()
    for url in urls:
        if urlsplit(url).hostname == host:
            candidates.add(checked_url(url, frozenset({host})))
    if len(candidates) != 1:
        raise PublicSourceError("The source did not publish one unambiguous download link")
    file_url = candidates.pop()
    filename = unquote(urlsplit(file_url).path.rsplit("/", 1)[-1])
    archive = filename.rsplit(".", 1)[-1].lower()
    if (
        archive not in ("zip", "7z")
        or "/" in filename
        or "\\" in filename
        or any(ord(c) < 32 for c in filename)
        or filename in (".zip", "..zip", ".7z", "..7z")
    ):
        raise PublicSourceError(f"Unsupported archive filename: {filename!r}; supported formats are ZIP and 7z")
    if archive == "7z":
        ensure_7z_available()
    return DownloadPlan(
        provider=provider,
        page_url=page_url,
        file_url=file_url,
        filename=filename,
        archive=archive,
        region=download_region(filename),
    )


def _size(page: PublicPage) -> str | None:
    match = re.search(r"(?:File\s+Size|Size)\s*:?\s*([0-9]+(?:[.,][0-9]+)?\s*(?:[KMG]i?B))\b", page.text, re.I)
    return match[1].strip() if match else None


class _SearchDownloads:
    page_hosts: frozenset[str]
    origin: str

    def search(self, title: str, platform: str) -> list[DownloadPlan]:
        url = self.origin + "/search?" + urlencode({"search_term_string": base_title(title)})
        urls = []
        for number in range(1, 7):
            page = PublicPage(self._http.read_html(url))
            for link in page.links:
                if title_key(link.get("title", "")) != title_key(title):
                    continue
                try:
                    target = _game_page(urljoin(url, link.get("href", "")), self.page_hosts)
                except ValueError:
                    continue
                if urlsplit(target).path.split("/")[2] == platform and target not in urls:
                    urls.append(target)
            next_page = None
            for link in page.links:
                try:
                    target = checked_url(urljoin(url, link.get("href", "")), self.page_hosts)
                except ValueError:
                    continue
                parsed = urlsplit(target)
                if parsed.path == "/search" and parse_qs(parsed.query) == {
                    "search_term_string": [base_title(title)],
                    "currentpage": [str(number + 1)],
                }:
                    next_page = target
                    break
            if next_page is None:
                break
            url = next_page
        plans = []
        errors = []
        for target in urls:
            try:
                plans.append(self.resolve(target))
            except (PublicSourceError, URLError) as exc:
                _logger.exception("Published download resolution failed: %s", target)
                errors.append(str(exc))
        if errors and not plans:
            raise PublicSourceError("Published downloads unavailable: " + "; ".join(errors))
        return plans

    def resolve(self, page_url: str) -> DownloadPlan:
        raise NotImplementedError

    _http: PublicHttpAdapter


class RomspediaDownloadAdapter(_SearchDownloads):
    """Resolve only the game page's published slow-download link and file link."""

    page_hosts = frozenset({"www.romspedia.com", "romspedia.com"})
    file_host = "downloads.romspedia.com"
    origin = "https://www.romspedia.com"

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
        plan = _archive_plan(
            "romspedia",
            page_url,
            [urljoin(landing_url, link["href"]) for link in landing.links if link.get("href")],
            self.file_host,
        )

        return replace(plan, size=_size(page))


class RomsdlDownloadAdapter(_SearchDownloads):
    """Submit the visible download form and read its literal countdown target."""

    page_hosts = frozenset({"romsdl.com", "www.romsdl.com"})
    file_host = "downloads.retrostic.com"
    origin = "https://romsdl.com"

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
        return replace(_archive_plan("romsdl", page_url, targets, self.file_host), size=_size(page))
