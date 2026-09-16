from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from adapters.public_catalogue.emuparadise import EmuparadiseCatalogueAdapter
from adapters.public_catalogue.vimm import VimmDownloadAdapter
from adapters.public_catalogue.http import PublicSourceError


def test_platform_filter_sent_and_enforced_on_mixed_response():
    http = Mock()
    http.read_html.return_value = '<a data-filter="41" href="/Sony_Playstation_2_ISOs/Game/1">Game ISO</a><a data-filter="2" href="/Sony_Playstation_ISOs/Game/2">Game ISO</a>'
    result = EmuparadiseCatalogueAdapter(http=http).search("Game", "ps2")
    assert [item.external_id for item in result] == ["1"]
    assert parse_qs(urlsplit(http.read_html.call_args.args[0]).query)["sysid"] == ["41"]
    assert http.read_html.call_count == 1


@pytest.mark.parametrize("platform", ["ps3", "switch"])
def test_unsupported_catalogue_platform_never_falls_back(platform):
    http = Mock()
    assert EmuparadiseCatalogueAdapter(http=http).search("Game", platform) == []
    http.read_html.assert_not_called()


def test_vimm_search_sends_platform_and_matches_title():
    http = Mock()
    http.read_html.return_value = '<a href="/vault/1">Homebrew</a><a href="/vault/2">Homebrew 2</a>'
    adapter = VimmDownloadAdapter(http=http)
    adapter.resolve = Mock(return_value=Mock(platform="gameboy"))
    assert len(adapter.search("Homebrew (USA)", "gameboy")) == 1
    assert parse_qs(urlsplit(http.read_html.call_args.args[0]).query)["system"] == ["GB"]
    adapter.resolve.assert_called_once_with("https://vimm.net/vault/1")


def test_vimm_published_form_and_metadata():
    http = Mock()
    http.read_html.return_value = '<form><input name="system" value="GB"></form><form id="dl_form" action="//dl2.vimm.net/"><input name="mediaId" value="123"></form>'
    http.archive_metadata.return_value = ("Homebrew (USA).zip", "1 MiB")
    plan = VimmDownloadAdapter(http=http).resolve("https://vimm.net/vault/1")
    assert plan.file_url == "https://dl2.vimm.net/?mediaId=123"
    assert plan.platform == "gameboy"
    assert plan.region == "USA"
    http.archive_metadata.assert_called_once_with(plan.file_url, referer=plan.page_url)


def test_vimm_challenge_is_explicit_and_never_submitted():
    http = Mock()
    http.read_html.return_value = '<form id="turnstile-form" action="/vault/1" method="POST"></form>'
    with pytest.raises(PublicSourceError, match="human verification"):
        VimmDownloadAdapter(http=http).resolve("https://vimm.net/vault/1")
    http.archive_metadata.assert_not_called()


def test_vimm_form_rejects_other_origins():
    http = Mock()
    http.read_html.return_value = '<form><input name="system" value="GB"></form><form id="dl_form" action="https://example.org/"><input name="mediaId" value="123"></form>'
    with pytest.raises(PublicSourceError):
        VimmDownloadAdapter(http=http).resolve("https://vimm.net/vault/1")
    http.archive_metadata.assert_not_called()
