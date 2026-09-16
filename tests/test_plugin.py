import pytest
import main


@pytest.mark.asyncio
async def test_installation_setting_persists_and_blocks_install_until_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(main.decky, "DECKY_USER_HOME", str(tmp_path))
    plugin = main.Plugin()
    await plugin._main()
    try:
        assert (await plugin.get_emulator_installation())["selection"] == "auto"
        assert (await plugin.save_emulator_installation("emudeck"))["restart_required"]
        state = await plugin.get_emulator_installation()
        assert state["selection"] == "emudeck"
        assert state["active_selection"] == "auto"
        assert (await plugin.start_download(42))["reason"] == "restart_required"
        assert plugin._runtime.persistence.load_settings()["emulator_installation"] == "emudeck"
        assert not hasattr(plugin, "connect_with_credentials")
        assert not hasattr(plugin, "start_sync")
    finally:
        await plugin._unload()


@pytest.mark.asyncio
async def test_release_failure_is_returned_and_logged_with_traceback(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(main.decky, "DECKY_USER_HOME", str(tmp_path))

    def fail(home):
        raise OSError("connection interrupted")

    monkeypatch.setattr(main, "download_latest_release", fail)
    plugin = main.Plugin()
    await plugin._main()
    try:
        result = await plugin.download_latest_release()
        assert not result["success"]
        assert "connection interrupted" in result["message"]
        assert any(record.exc_info for record in caplog.records if "release download failed" in record.message)
    finally:
        await plugin._unload()
