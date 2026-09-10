"""Unsupported sessions must not enqueue a disruptive worker."""

from types import SimpleNamespace
from unittest.mock import Mock

from adapters.steam_rom_manager import SteamRomManagerAdapter


def test_missing_dependency_does_not_start_worker(monkeypatch, tmp_path):
    adapter = SteamRomManagerAdapter(
        installation=SimpleNamespace(kind="emudeck"), user_home=str(tmp_path), data_dir=str(tmp_path)
    )
    monkeypatch.setattr("adapters.steam_rom_manager.shutil.which", lambda name: None)
    run = Mock()
    monkeypatch.setattr("adapters.steam_rom_manager.subprocess.run", run)
    result = adapter.start()
    assert result["success"] is False
    assert "systemd-run" in result["message"]
    run.assert_not_called()


def test_retrodeck_never_starts_srm(monkeypatch, tmp_path):
    adapter = SteamRomManagerAdapter(
        installation=SimpleNamespace(kind="retrodeck"), user_home=str(tmp_path), data_dir=str(tmp_path)
    )
    run = Mock()
    monkeypatch.setattr("adapters.steam_rom_manager.subprocess.run", run)
    assert adapter.status() == {"enabled": False, "ready": False, "busy": False}
    assert adapter.start()["success"] is False
    run.assert_not_called()
