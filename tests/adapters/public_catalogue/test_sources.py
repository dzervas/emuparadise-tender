"""Public-source contract fixtures use synthetic homebrew titles and bytes."""

from unittest.mock import Mock

import pytest

from adapters.public_catalogue.downloads import RomsdlDownloadAdapter, RomspediaDownloadAdapter
from adapters.public_catalogue.emuparadise import EmuparadiseCatalogueAdapter
from adapters.public_catalogue.http import PublicSourceError, checked_url


def test_romspedia_follows_published_links_not_ads():
    http = Mock()
    http.read_html.side_effect = [
        '<a href="https://ads.example/installer.exe">Download</a>'
        '<a id="btnDownload_slow" href="/roms/gameboy/homebrew/download">Slow</a>',
        '<a href="https://downloads.romspedia.com/roms/Homebrew (World).zip">click here</a>',
    ]
    plan = RomspediaDownloadAdapter(http=http).resolve("https://www.romspedia.com/roms/gameboy/homebrew")
    assert plan.filename == "Homebrew (World).zip"
    assert plan.file_url == "https://downloads.romspedia.com/roms/Homebrew%20(World).zip"
    assert plan.provider == "romspedia"
    assert http.read_html.call_args.args == ("https://www.romspedia.com/roms/gameboy/homebrew/download",)


def test_romsdl_submits_fresh_form_values_without_executing_javascript():
    http = Mock()
    http.read_html.side_effect = [
        '<form id="dl" method="post" action="/roms/gameboy/homebrew-1/download">'
        '<input name="rom_url" value="homebrew-1"><input name="console_url" value="gameboy">'
        '<input name="session" value="fresh-token"></form>',
        '<script>window.location.href = "https://downloads.retrostic.com/roms/Homebrew.zip";</script>',
    ]
    plan = RomsdlDownloadAdapter(http=http).resolve("https://romsdl.com/roms/gameboy/homebrew-1")
    assert plan.file_url == "https://downloads.retrostic.com/roms/Homebrew.zip"
    assert http.read_html.call_args.kwargs == {
        "fields": {"rom_url": "homebrew-1", "console_url": "gameboy", "session": "fresh-token"}
    }


@pytest.mark.parametrize(
    "html",
    [
        "<h1>Verify you are human</h1>",
        '<a id="btnDownload_slow" href="https://evil.example/roms/gameboy/homebrew/download">Download</a>',
        '<a id="btnDownload_slow" href="/account/login">Download</a>',
    ],
)
def test_romspedia_rejects_changed_or_protected_flow(html):
    http = Mock()
    http.read_html.return_value = html
    with pytest.raises(PublicSourceError):
        RomspediaDownloadAdapter(http=http).resolve("https://www.romspedia.com/roms/gameboy/homebrew")
    assert http.read_html.call_count == 1


def test_ambiguous_direct_links_are_not_guessed():
    http = Mock()
    http.read_html.side_effect = [
        '<a id="btnDownload_slow" href="/roms/gameboy/homebrew/download">Download</a>',
        '<a href="https://downloads.romspedia.com/roms/a.zip">A</a>'
        '<a href="https://downloads.romspedia.com/roms/b.zip">B</a>',
    ]
    with pytest.raises(PublicSourceError):
        RomspediaDownloadAdapter(http=http).resolve("https://www.romspedia.com/roms/gameboy/homebrew")


def test_romsdl_never_fabricates_session():
    http = Mock()
    http.read_html.return_value = (
        '<form id="dl" method="post" action="/roms/gameboy/homebrew-1/download">'
        '<input name="rom_url" value="homebrew-1"><input name="console_url" value="gameboy"></form>'
    )
    with pytest.raises(PublicSourceError):
        RomsdlDownloadAdapter(http=http).resolve("https://romsdl.com/roms/gameboy/homebrew-1")
    assert http.read_html.call_count == 1


def test_catalogue_is_independent_of_download_availability():
    http = Mock()
    http.read_html.return_value = (
        '<meta property="og:title" content="Homebrew ROM for GB">'
        '<meta property="og:description" content="A new game">'
        "<h1>Homebrew ROM</h1><p>Downloads unavailable</p>"
    )
    entry = EmuparadiseCatalogueAdapter(http=http).get_entry(
        "https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Homebrew/123"
    )
    assert (entry.external_id, entry.title, entry.platform) == ("123", "Homebrew", "Nintendo_Game_Boy_ROMs")
    assert entry.description == "A new game"


@pytest.mark.parametrize(
    "url",
    [
        "http://romsdl.com/a",
        "https://romsdl.com.evil.example/a",
        "https://romsdl.com@evil.example/a",
        "https://user:password@romsdl.com/a",
        "https://romsdl.com:8443/a",
        "https://127.0.0.1/a",
        "https://romsdl.com/\\evil",
        "https://romsdl.com/\r\nheader",
    ],
)
def test_origin_boundary(url):
    with pytest.raises(PublicSourceError):
        checked_url(url, frozenset({"romsdl.com"}))
