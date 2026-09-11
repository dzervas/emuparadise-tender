"""Public search fixtures enforce five results, platform matching, and validated links."""

from unittest.mock import Mock

import pytest
from models.content_provider import DownloadPlan

from adapters.public_catalogue.downloads import RomspediaDownloadAdapter
from adapters.public_catalogue.emuparadise import EmuparadiseCatalogueAdapter
from domain.catalogue_matching import base_title, download_region


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


@pytest.mark.parametrize(
    "title",
    [
        "Crash Bash (E) ISO[SCES-02834]",
        "Crash Bash (USA) ROM [SCUS-94570]",
        "Crash Bash ISO[SCES-02834] Roms",
        "Crash Bash",
    ],
)
def test_catalogue_dump_tags_do_not_reach_provider_search(title):
    assert base_title(title) == "Crash Bash"


@pytest.mark.parametrize(
    "filename,region",
    [
        ("Crash Bash (E) [SCES-02834].7z", "Europe"),
        ("Crash Bash [NTSC-U] [SCUS-94570].rar", "USA"),
        ("Crash Bash (USA, Europe) (En,Fr).7z", "USA, Europe"),
        ("Crash Bash (En,Fr) [SCUS-94570].zip", None),
    ],
)
def test_regions_come_from_download_tags(filename, region):
    assert download_region(filename) == region


def test_search_returns_variants_beyond_first_page_and_first_two_results():
    http = Mock()
    http.read_html.side_effect = [
        '<a href="/roms/playstation-1/crash-e" title="Crash Bash (E) ISO[SCES-02834] Roms">EU</a>'
        '<a href="/roms/playstation-1/crash-u" title="Crash Bash (U) ROM">US</a>'
        '<a href="/search?currentpage=2&search_term_string=Crash+Bash">Next</a>',
        '<a href="/roms/playstation-1/crash-j" title="Crash Bash (Japan) ROM">JP</a>'
        '<a href="/roms/playstation-2/crash-e" title="Crash Bash ROM">Wrong platform</a>'
        '<a href="/roms/playstation-1/crash-2" title="Crash Bash 2 ROM">Wrong game</a>',
    ]
    adapter = RomspediaDownloadAdapter(http=http)
    adapter.resolve = Mock(side_effect=lambda url: DownloadPlan("romspedia", url, "https://files/game.zip", "game.zip"))
    plans = adapter.search("Crash Bash (E) ISO[SCES-02834]", "playstation-1")
    assert len(plans) == 3
    assert http.read_html.call_args_list[0].args[0].endswith("search_term_string=Crash+Bash")
    assert [plan.page_url.rsplit("/", 1)[-1] for plan in plans] == ["crash-e", "crash-u", "crash-j"]
