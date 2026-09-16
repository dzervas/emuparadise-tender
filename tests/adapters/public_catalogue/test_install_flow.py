import asyncio
import logging
import zipfile
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import bootstrap as wiring
from models.content_provider import CatalogueEntry, DownloadPlan
from fakes.fake_retrodeck_paths import FakeRetroDeckPaths
from fakes.fake_core_info_provider import FakeCoreInfoProvider


def test_import_install_and_delete_preserves_neighbor_files(tmp_path, monkeypatch):
    async def run():
        root = tmp_path / "roms"
        (root / "gb").mkdir(parents=True)
        neighbor = root / "gb/Neighbor.gb"
        neighbor.write_bytes(b"existing")
        paths = FakeRetroDeckPaths(roms=str(root))
        paths.kind = "retrodeck"
        paths.choose = lambda: None
        monkeypatch.setattr(wiring, "EmulatorInstallationAdapter", Mock(return_value=paths))
        core = FakeCoreInfoProvider()
        core.get_supported_extensions = lambda system: [".gb"]
        core.system_supports_m3u = lambda system: False
        monkeypatch.setattr(wiring, "InstallationCatalogueAdapter", Mock(return_value=core))
        runtime = wiring.bootstrap(
            user_home=str(tmp_path), plugin_dir=str(tmp_path), emit=AsyncMock(), logger=logging.getLogger("test")
        )
        entry = CatalogueEntry(
            "emuparadise",
            "1",
            "https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Homebrew/1",
            "Homebrew",
            "Nintendo_Game_Boy_ROMs",
        )
        plan = DownloadPlan(
            "romspedia",
            "https://www.romspedia.com/roms/gameboy/homebrew",
            "https://downloads.romspedia.com/Homebrew.zip",
            "Homebrew.zip",
        )
        runtime.search._config = replace(
            runtime.search._config,
            catalogue=Mock(get_entry=Mock(return_value=entry)),
            resolvers={"romspedia": Mock(resolve=Mock(return_value=plan))},
        )
        runtime.api._resolvers = runtime.search._config.resolvers

        def transfer(url, dest, callback=None, **kwargs):
            with zipfile.ZipFile(dest, "w") as archive:
                archive.writestr("wrapper/Homebrew.gb", b"synthetic test game")

        runtime.api._transports["romspedia"] = Mock(download_zip=transfer)
        imported = await runtime.search.import_entry(entry.page_url, "romspedia", plan.page_url)
        assert imported["success"], imported
        rom_id = imported["rom_id"]
        assert (await runtime.search.bind_shortcut(rom_id, 123456))["success"]
        started = await runtime.downloads.start_download(rom_id)
        assert started["success"], started
        await runtime.downloads.task_for_rom(rom_id)
        installed = runtime.downloads.get_installed_rom(rom_id)
        assert installed, runtime.downloads.get_download_queue()
        assert (root / "gb/Homebrew.gb").read_bytes() == b"synthetic test game"
        removed = await runtime.removal.remove_rom(rom_id)
        assert removed["success"], removed
        assert not (root / "gb/Homebrew.gb").exists()
        assert neighbor.read_bytes() == b"existing"
        await runtime.downloads.shutdown()

    asyncio.run(run())
