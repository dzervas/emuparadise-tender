"""Public catalogue imports use the real SQLite/install/delete pipeline."""

import os
import zipfile
from dataclasses import replace
from unittest.mock import Mock

from models.content_provider import CatalogueEntry, DownloadPlan

from adapters.public_catalogue.router import ContentApiRouter
from domain.provider_identity import PUBLIC_ID_START


async def test_public_import_download_and_delete_preserves_other_files(harness):
    plugin = harness.plugin
    catalogue = plugin._catalogue_service
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
    assert (await plugin.bind_catalogue_shortcut(rom_id, 123456789))["success"]
    again = await plugin.import_catalogue_entry(entry.page_url, "romspedia", plan.page_url)
    assert again["rom_id"] == rom_id
    assert again["app_id"] == 123456789
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
    removed = await plugin.remove_rom(rom_id)
    assert removed["success"], removed
    assert not os.path.exists(installed["file_path"])
    with open(other, "rb") as file:
        assert file.read() == b"untouched"
    assert plugin._download_service.get_installed_rom(rom_id) is None
    with catalogue._config.uow_factory() as uow:
        assert uow.roms.get(rom_id).shortcut_app_id == 123456789


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
