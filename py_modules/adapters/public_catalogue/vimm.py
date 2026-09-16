"""Vimm's published Vault links; human checks remain an explicit unavailable result."""

import logging
import re
from dataclasses import replace
from typing import ClassVar
from urllib.parse import urlencode, urljoin, urlsplit

from models.content_provider import DownloadPlan

from adapters.public_catalogue.downloads import _archive_plan, _size
from adapters.public_catalogue.http import PublicSourceError, checked_url
from adapters.public_catalogue.page import PublicPage
from adapters.seven_zip import ensure_7z_available
from domain.catalogue_matching import base_title, download_region, title_key

logger = logging.getLogger(__name__)


class VimmDownloadAdapter:
    page_hosts = frozenset({"vimm.net", "www.vimm.net"})
    file_hosts = frozenset({"dl1.vimm.net", "dl2.vimm.net", "dl3.vimm.net"})
    systems: ClassVar[dict[str, str]] = {
        "playstation-1": "PS1",
        "playstation-2": "PS2",
        "playstation-3": "PS3",
        "playstation-portable": "PSP",
        "nintendo-gamecube": "GameCube",
        "nintendo-wii": "Wii",
        "gameboy": "GB",
        "gameboy-color": "GBC",
        "gameboy-advance": "GBA",
        "nintendo": "NES",
        "super-nintendo": "SNES",
        "nintendo-64": "N64",
        "nintendo-ds": "DS",
        "sega-genesis": "Genesis",
        "sega-dreamcast": "Dreamcast",
    }

    def __init__(self, *, http):
        self._http = http

    def _page(self, url):
        page = PublicPage(self._http.read_html(url))
        if (
            any(attrs.get("id") == "turnstile-form" for attrs, _ in page.forms)
            or "Checking if you are human" in page.text
        ):
            raise PublicSourceError(
                "Vimm requires a human verification in a browser; automatic downloads are unavailable"
            )
        return page

    def search(self, title, platform):
        if platform not in self.systems:
            return []
        url = "https://vimm.net/vault/?" + urlencode(
            {"p": "list", "system": self.systems[platform], "q": base_title(title)}
        )
        page = self._page(url)
        targets = set()
        for link in page.links:
            if title_key(link.get("text", "")) != title_key(title):
                continue
            target = checked_url(urljoin(url, link.get("href", "")), self.page_hosts)
            if re.fullmatch(r"/vault/\d+", urlsplit(target).path):
                targets.add(target)
        plans, errors = [], []
        for target in sorted(targets):
            try:
                plan = self.resolve(target)
                if plan.platform == platform:
                    plans.append(plan)
            except PublicSourceError as exc:
                logger.exception("Vimm source unavailable: %s", target)
                errors.append(str(exc))
        if errors and not plans:
            raise PublicSourceError(errors[0])
        return plans

    def resolve(self, page_url):
        page_url = checked_url(page_url, self.page_hosts)
        if not re.fullmatch(r"/vault/\d+", urlsplit(page_url).path) or urlsplit(page_url).query:
            raise PublicSourceError("Choose a Vimm Vault game page")
        page = self._page(page_url)
        system = next((fields.get("system") for _, fields in page.forms if fields.get("system")), None)
        platform = next((key for key, value in self.systems.items() if value == system), None)
        if platform is None:
            raise PublicSourceError("Vimm did not identify the game's platform")
        forms = [(attrs, fields) for attrs, fields in page.forms if attrs.get("id") == "dl_form"]
        if len(forms) == 1:
            attrs, fields = forms[0]
            if attrs.get("method", "get").lower() != "get" or not fields.get("mediaId", "").isdigit():
                raise PublicSourceError("Vimm's public download form has changed")
            action = checked_url(urljoin(page_url, attrs.get("action", "")), self.file_hosts)
            file_url = action + ("&" if "?" in action else "?") + urlencode(fields)
            filename, size = self._http.archive_metadata(file_url, referer=page_url)
            archive = filename.rsplit(".", 1)[-1].lower()
            if archive == "7z":
                ensure_7z_available()
            return DownloadPlan(
                provider="vimm",
                page_url=page_url,
                file_url=file_url,
                filename=filename,
                archive=archive,
                size=size or _size(page),
                region=download_region(filename),
                platform=platform,
            )
        urls = [urljoin(page_url, link["href"]) for link in page.links if link.get("href")]
        candidates = [url for url in urls if urlsplit(url).hostname in self.file_hosts]
        if len(set(candidates)) != 1:
            raise PublicSourceError("Vimm has not published a downloadable archive for this game")
        plan = _archive_plan("vimm", page_url, candidates, urlsplit(candidates[0]).hostname)
        return replace(plan, size=_size(page), platform=platform)
