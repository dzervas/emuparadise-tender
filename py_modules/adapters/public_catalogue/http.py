"""Unauthenticated public-source transport with explicit origin boundaries."""

from __future__ import annotations

import http.cookiejar
import logging
import os
import ssl
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ca-certificates/extracted/tls-ca-bundle.pem",
    "/etc/ssl/cert.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
)
_logger = logging.getLogger(__name__)


def _system_ssl_context() -> ssl.SSLContext:
    """Verify against OS roots even when frozen OpenSSL defaults point elsewhere."""
    context = ssl.create_default_context()
    for bundle in _SYSTEM_CA_BUNDLES:
        if os.path.isfile(bundle):
            context.load_verify_locations(cafile=bundle)
            _logger.info("Public catalogue HTTPS uses system CA bundle: %s", bundle)
            break
    else:
        _logger.info("Public catalogue HTTPS uses OpenSSL default CA paths: %s", ssl.get_default_verify_paths())
    return context


class PublicSourceError(ValueError):
    """A public source cannot supply a supported file through its published flow."""


def checked_url(url: str, hosts: frozenset[str]) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or any(ord(c) < 32 for c in url)
        or "\\" in url
    ):
        raise PublicSourceError("The source returned an unsupported URL")
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
            urllib.parse.quote(parsed.query, safe="%=&?/:@!$'()*+,;~-._"),
            "",
        )
    )


class _SourceRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts: frozenset[str]) -> None:
        super().__init__()
        self._hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, checked_url(newurl, self._hosts))


class PublicHttpAdapter:
    """No RomM credentials, script execution, or arbitrary-origin requests."""

    def __init__(self, *, hosts: frozenset[str], user_agent: str) -> None:
        self._hosts = hosts
        self._user_agent = user_agent
        self._opener = urllib.request.build_opener(
            _SourceRedirects(hosts),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=_system_ssl_context()),
        )

    def read_html(self, url: str, *, fields: dict[str, str] | None = None) -> str:
        request = urllib.request.Request(
            checked_url(url, self._hosts),
            data=urllib.parse.urlencode(fields).encode() if fields is not None else None,
            headers={"User-Agent": self._user_agent, "Accept": "text/html"},
        )
        with self._opener.open(request, timeout=30) as response:
            checked_url(response.url, self._hosts)
            if response.headers.get_content_type() != "text/html":
                raise PublicSourceError("Expected a public catalogue page")
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise PublicSourceError("The source page is too large")
            return body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    def download_zip(
        self,
        url: str,
        dest: str,
        progress_callback: Callable[[int, int], None] | None = None,
        *,
        resume: bool = False,
        on_meta: Callable[[bool], None] | None = None,
    ) -> None:
        if resume:
            raise PublicSourceError("This source requires restarting the download")
        request = urllib.request.Request(checked_url(url, self._hosts), headers={"User-Agent": self._user_agent})
        with self._opener.open(request, timeout=30) as response:
            checked_url(response.url, self._hosts)
            if response.status != 200 or response.headers.get_content_type() in (
                "text/html",
                "application/xhtml+xml",
                "application/json",
                "text/plain",
            ):
                raise PublicSourceError("The source returned a page instead of an archive")
            first = response.read(6)
            if not (first.startswith(b"PK\x03\x04") or first == b"7z\xbc\xaf\x27\x1c"):
                raise PublicSourceError("The source did not return a supported ZIP or 7z archive")
            length = response.headers.get("Content-Length")
            total = int(length) if length else 0
            if on_meta:
                on_meta(False)
            received = len(first)
            if progress_callback:
                progress_callback(received, total)
            with open(dest, "wb") as output:
                output.write(first)
                while chunk := response.read(256 * 1024):
                    output.write(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, total)
            if total and received != total:
                raise PublicSourceError("The source closed an incomplete transfer")
