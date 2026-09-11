"""Public search fixtures enforce five results, platform matching, and validated links."""

from unittest.mock import Mock

import pytest

from adapters.public_catalogue.downloads import RomspediaDownloadAdapter
from adapters.public_catalogue.emuparadise import EmuparadiseCatalogueAdapter


def test_catalogue_search_limits_deduplicates_and_excludes_external_links():
    http = Mock()
    http.read_html.return_value = (
        "".join(
            f'<a data-filter="12" href="/Nintendo_Game_Boy_ROMs/Game_{i}/{i}">Game {i} ROM</a>' for i in range(1, 9)
        )
        + '<a data-filter="12" href="https://evil.example/Nintendo_Game_Boy_ROMs/Game/42">Game ROM</a>'
    )
    results = EmuparadiseCatalogueAdapter(http=http).search("Game & More")
    assert len(results) == 5
    assert results[0].title == "Game 1"
    assert all(item.provider == "emuparadise" for item in results)
    assert http.read_html.call_args.args[0].endswith("query=Game+%26+More")


def test_search_rejects_short_query_without_network():
    http = Mock()
    with pytest.raises(ValueError):
        EmuparadiseCatalogueAdapter(http=http).search("x")
    http.read_html.assert_not_called()


def test_download_search_matches_title_and_platform_and_reads_provider_size():
    http = Mock()
    http.read_html.side_effect = [
        '<a href="/roms/nintendo/homebrew" title="Homebrew ROM">Wrong platform</a>'
        '<a href="/roms/gameboy/homebrew-2" title="Homebrew 2 ROM">Wrong game</a>'
        '<a href="https://evil.example/roms/gameboy/homebrew" title="Homebrew ROM">External</a>'
        '<a href="/roms/gameboy/homebrew" title="Homebrew ROM">Homebrew</a>',
        "<h1>Homebrew</h1><div>Size:</div><div>20.5KB</div>"
        '<a id="btnDownload_slow" href="/roms/gameboy/homebrew/download">Download</a>',
        '<a href="https://downloads.romspedia.com/roms/Homebrew.zip">Download</a>',
    ]
    plans = RomspediaDownloadAdapter(http=http).search("Homebrew (USA)", "gameboy")
    assert len(plans) == 1
    assert plans[0].size == "20.5KB"
    assert plans[0].filename == "Homebrew.zip"
    assert http.read_html.call_count == 3


def test_download_search_follows_only_published_next_page():
    http = Mock()
    http.read_html.side_effect = [
        '<a href="https://evil.example/search?currentpage=2&search_term_string=Homebrew">Bad</a>'
        '<a href="/search?currentpage=2&search_term_string=Homebrew">Next</a>',
        '<a href="/roms/gameboy/homebrew" title="Homebrew ROM">Homebrew</a>',
        '<a id="btnDownload_slow" href="/roms/gameboy/homebrew/download">Download</a>',
        '<a href="https://downloads.romspedia.com/roms/Homebrew.zip">Download</a>',
    ]
    plans = RomspediaDownloadAdapter(http=http).search("Homebrew", "gameboy")
    assert len(plans) == 1
    assert plans[0].size is None
    assert (
        http.read_html.call_args_list[1].args[0]
        == "https://www.romspedia.com/search?currentpage=2&search_term_string=Homebrew"
    )
