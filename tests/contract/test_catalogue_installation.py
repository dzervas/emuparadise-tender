"""Public catalogue imports use the real SQLite/install/delete pipeline."""

import os
import zipfile
from dataclasses import replace
from unittest.mock import Mock

import pytest
from models.content_provider import CatalogueEntry, DownloadPlan

from adapters.public_catalogue.router import ContentApiRouter
from domain.provider_identity import PUBLIC_ID_START


@pytest.mark.parametrize("srm_owned", [False, True])
async def test_public_import_download_and_delete_preserves_other_files(harness, srm_owned):
    plugin = harness.plugin
    catalogue = plugin._catalogue_service
    catalogue._config = replace(catalogue._config, shortcut_owner="srm" if srm_owned else "tender")
    plugin._download_service._install_recorder._external_shortcuts = srm_owned
    entry = CatalogueEntry(
        "emuparadise",
        "homebrew-1",
        "https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Homebrew/1",
        "Homebrew",
        "Nintendo_Game_Boy_ROMs",
    )
    plan = DownloadPlan(
        "romspedia",
        "https://www.romspedia.com/roms/gameboy/homebrew",
        "https://downloads.romspedia.com/roms/Homebrew.zip",
        "Homebrew.zip",
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
        with zipfile.ZipFile(dest, "w") as archive:
            archive.writestr("Homebrew.gb", b"legal synthetic homebrew fixture")
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
    os.makedirs(os.path.join(root, "gb"), exist_ok=True)
    other = os.path.join(root, "gb", "Other.gb")
    with open(other, "wb") as file:
        file.write(b"untouched")
    started = await plugin.start_download(rom_id)
    assert started["success"], started
    await plugin._download_service._download_tasks[rom_id]
    installed = plugin._download_service.get_installed_rom(rom_id)
    assert installed, plugin._download_service.get_download_queue()
    assert os.path.commonpath([installed["file_path"], os.path.join(root, "gb")]) == os.path.join(root, "gb")
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
    blocked = await plugin.start_download(42)
    assert blocked["reason"] == "restart_required"
    blocked_import = await plugin.import_catalogue_entry("unused", "romspedia", "unused")
    assert blocked_import["reason"] == "restart_required"


async def test_catalogue_download_search_preserves_other_provider_results(harness):
    catalogue = harness.plugin._catalogue_service
    reader = Mock()
    reader.get_entry.return_value = CatalogueEntry(
        "emuparadise", "1", "https://catalogue/game", "Homebrew", "Nintendo_Game_Boy_ROMs"
    )
    working, broken = Mock(), Mock()
    working.search.return_value = [
        DownloadPlan("romspedia", "https://source/game", "https://source/file", "Homebrew.zip")
    ]
    broken.search.side_effect = ValueError("Source unavailable")
    catalogue._config = replace(catalogue._config, catalogue=reader, resolvers={"romspedia": working, "romsdl": broken})
    result = await harness.plugin.get_catalogue_downloads("https://catalogue/game")
    assert result["success"]
    assert result["items"][0]["filename"] == "Homebrew.zip"
    assert "romsdl" in result["messages"][0]
    working.search.assert_called_once_with("Homebrew", "gameboy")
