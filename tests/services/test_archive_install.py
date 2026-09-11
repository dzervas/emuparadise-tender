"""Flat archive publication must preserve neighbors and reject collisions."""

from unittest.mock import Mock

import pytest

from adapters.download_file import DownloadFileAdapter
from domain.provider_identity import PUBLIC_ID_START
from services.archive_install import archive_cleanup_dirs, record_single_archive


def test_nested_single_file_is_published_with_file_ownership(tmp_path):
    stage = tmp_path / "stage"
    (stage / "wrapper").mkdir(parents=True)
    (stage / "wrapper/Game.iso").write_bytes(b"game")
    recorder = Mock()
    recorder.do_record_install.return_value = (str(tmp_path / "Game.iso"), None)
    record_single_archive(DownloadFileAdapter(), recorder, str(stage), PUBLIC_ID_START, {}, "ps2")
    assert (tmp_path / "Game.iso").read_bytes() == b"game"
    assert not stage.exists()
    assert recorder.do_record_install.call_args.kwargs["rom_dir"] is None
    recorder.do_record_install.call_args.kwargs["cleanup"]()
    assert not (tmp_path / "Game.iso").exists()


def test_existing_destination_is_preserved(tmp_path):
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "Game.iso").write_bytes(b"new")
    (tmp_path / "Game.iso").write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        record_single_archive(DownloadFileAdapter(), Mock(), str(stage), PUBLIC_ID_START, {}, "ps2")
    assert (tmp_path / "Game.iso").read_bytes() == b"existing"


def test_recording_failure_removes_only_published_file(tmp_path):
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "Game.iso").write_bytes(b"game")
    (tmp_path / "Other.iso").write_bytes(b"other")
    recorder = Mock()
    recorder.do_record_install.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        record_single_archive(DownloadFileAdapter(), recorder, str(stage), PUBLIC_ID_START, {}, "ps2")
    assert not (tmp_path / "Game.iso").exists()
    assert (tmp_path / "Other.iso").read_bytes() == b"other"


def test_multiple_files_keep_directory_ownership(tmp_path):
    (tmp_path / "Game.bin").write_bytes(b"bin")
    (tmp_path / "Game.cue").write_bytes(b"cue")
    recorder = Mock()
    assert record_single_archive(DownloadFileAdapter(), recorder, str(tmp_path), PUBLIC_ID_START, {}, "psx") is None
    recorder.do_record_install.assert_not_called()
    assert (tmp_path / "Game.bin").exists()


def test_flat_failure_cleanup_never_owns_platform_directory():
    assert archive_cleanup_dirs("/roms/ps2/Game.zip", "Game", "/roms/ps2/Game.iso") == {"/roms/ps2/Game"}
