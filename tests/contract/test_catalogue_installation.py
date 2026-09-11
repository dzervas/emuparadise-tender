"""Public catalogue imports use the real SQLite/install/delete pipeline."""

import json
import os
import zipfile
from dataclasses import replace
from unittest.mock import Mock

import pytest
from fakes.seven_zip_bytes import VALID
from models.content_provider import CatalogueEntry, DownloadPlan

from adapters.public_catalogue.router import ContentApiRouter
from domain.provider_identity import PUBLIC_ID_START


@pytest.mark.parametrize("archive", ["zip", "7z"])
@pytest.mark.parametrize("srm_owned", [False, True])
async def test_public_import_download_and_delete_preserves_other_files(harness, srm_owned, archive):
    system = "ps2" if archive == "7z" else "gb"
    section = "Sony_Playstation_2_ISOs" if archive == "7z" else "Nintendo_Game_Boy_ROMs"
    download_section = "playstation-2" if archive == "7z" else "gameboy"
    plugin = harness.plugin
    catalogue = plugin._catalogue_service
    catalogue._config = replace(catalogue._config, shortcut_owner="srm" if srm_owned else "tender")
    plugin._download_service._install_recorder._external_shortcuts = srm_owned
    entry = CatalogueEntry(
        "emuparadise",
        "homebrew-1",
        f"https://www.emuparadise.me/{section}/Homebrew/1",
        "Homebrew",
        section,
    )
    plan = DownloadPlan(
        "romspedia",
        f"https://www.romspedia.com/roms/{download_section}/homebrew",
        f"https://downloads.romspedia.com/roms/Homebrew.{archive}",
        f"Homebrew.{archive}",
        archive=archive,
    )
    reader = Mock()
    reader.get_entry.return_value = entry
    resolver = Mock()
    resolver.resolve.return_value = plan
    catalogue._config = replace(catalogue._config, catalogue=reader, resolvers={"romspedia": resolver})
    router = ContentApiRouter(
        romm=harness.romm, sources=catalogue._config.sources, resolvers={"romspedia": resolver}, transports={}
    )
    plugin._download_service._downloads = router
    plugin._download_service._catalogue = router

    def transfer(url, dest, callback=None, *, resume=False, on_meta=None):
        if archive == "7z":
            with open(dest, "wb") as output:
                output.write(VALID)
        else:
            with zipfile.ZipFile(dest, "w") as zipped:
                zipped.writestr("Homebrew.gb", b"legal synthetic homebrew fixture")
        if on_meta:
            on_meta(False)
        if callback:
            callback(os.path.getsize(dest), os.path.getsize(dest))

    router._transports["romspedia"] = Mock(download_zip=transfer)
    imported = await plugin.import_catalogue_entry(entry.page_url, "romspedia", plan.page_url)
    assert imported["success"], imported
    rom_id = imported["rom_id"]
    assert rom_id >= PUBLIC_ID_START
    assert (await plugin.bind_catalogue_shortcut(rom_id, 123456789))["success"] is not srm_owned
    again = await plugin.import_catalogue_entry(entry.page_url, "romspedia", plan.page_url)
    assert again["rom_id"] == rom_id
    assert again["app_id"] == (None if srm_owned else 123456789)
    root = plugin._retrodeck_paths.roms_path()
    os.makedirs(os.path.join(root, system), exist_ok=True)
    other = os.path.join(root, system, "Other.gb")
    with open(other, "wb") as file:
        file.write(b"untouched")
    started = await plugin.start_download(rom_id)
    assert started["success"], started
    await plugin._download_service._download_tasks[rom_id]
    installed = plugin._download_service.get_installed_rom(rom_id)
    assert installed, plugin._download_service.get_download_queue()
    assert os.path.commonpath([installed["file_path"], os.path.join(root, system)]) == os.path.join(root, system)
    assert os.path.isfile(installed["file_path"])
    listed = await plugin.list_catalogue_entries()
    assert any(item["rom_id"] == rom_id and item["installed"] for item in listed["items"])
    removed = await plugin.remove_rom(rom_id)
    assert removed["success"], removed
    assert not os.path.exists(installed["file_path"])
    with open(other, "rb") as file:
        assert file.read() == b"untouched"
    assert plugin._download_service.get_installed_rom(rom_id) is None
    with catalogue._config.uow_factory() as uow:
        assert uow.roms.get(rom_id).shortcut_app_id == (None if srm_owned else 123456789)


async def test_installation_change_requires_restart_before_new_downloads(harness):
    plugin = harness.plugin
    plugin._settings_service._available_installations = ("auto", "emudeck")
    changed = await plugin.save_emulator_installation("emudeck")
    assert changed["success"], changed
    assert changed["restart_required"]
    with open(os.path.join(harness.settings_dir, "settings.json")) as saved_file:
        assert json.load(saved_file)["emulator_installation"] == "emudeck"
    state = await plugin.get_emulator_installation()
    assert state["selection"] == "emudeck"
    assert state["active_selection"] == "auto"
    assert state["restart_required"]
    blocked = await plugin.start_download(42)
    assert blocked["reason"] == "restart_required"
    blocked_import = await plugin.import_catalogue_entry("unused", "romspedia", "unused")
    assert blocked_import["reason"] == "restart_required"


async def test_catalogue_download_search_preserves_other_provider_results(harness, caplog):
    catalogue = harness.plugin._catalogue_service
    reader = Mock()
    reader.get_entry.return_value = CatalogueEntry(
        "emuparadise", "1", "https://catalogue/game", "Homebrew", "Nintendo_Game_Boy_ROMs"
    )
    working, broken, empty = Mock(), Mock(), Mock()
    empty.search.return_value = []
    working.search.return_value = [
        DownloadPlan("romspedia", "https://source/game", "https://source/file", "Homebrew.zip")
    ]
    broken.search.side_effect = ValueError("Source unavailable")
    catalogue._config = replace(
        catalogue._config, catalogue=reader, resolvers={"romspedia": working, "romsdl": broken, "extra": empty}
    )
    with caplog.at_level("INFO"):
        result = await harness.plugin.get_catalogue_downloads("https://catalogue/game")
    assert result["success"]
    assert result["items"][0]["filename"] == "Homebrew.zip"
    assert "romsdl" in result["messages"][0]
    working.search.assert_called_once_with("Homebrew", "gameboy")
    broken.search.assert_called_once_with("Homebrew", "gameboy")
    empty.search.assert_called_once_with("Homebrew", "gameboy")
    assert [(item["provider"], item["success"], item["count"]) for item in result["provider_results"]] == [
        ("romspedia", True, 1),
        ("romsdl", False, 0),
        ("extra", True, 0),
    ]
    assert all(f"Searching download provider {name}:" in caplog.text for name in ("romspedia", "romsdl", "extra"))
    assert "Download provider extra: No matching published downloads" in caplog.text
    record = next(record for record in caplog.records if "download search failed" in record.message)
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], ValueError)
    assert record.exc_info[2] is not None
    assert "Traceback (most recent call last)" in caplog.text
    assert "ValueError: Source unavailable" in caplog.text
