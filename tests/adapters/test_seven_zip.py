from unittest.mock import Mock

import pytest
from fakes.seven_zip_bytes import SYMLINK, TRAVERSAL, VALID

from adapters.download_file import DownloadFileAdapter


def test_7z_dispatch_extracts_and_reports_progress(tmp_path):
    archive = tmp_path / "payload.zip.tmp"
    archive.write_bytes(VALID)
    dest = tmp_path / "owned"
    progress = Mock()
    DownloadFileAdapter().extract_zip(str(archive), str(dest), str(tmp_path), progress)
    assert (dest / "Homebrew.iso").read_bytes() == b"legal synthetic homebrew fixture"
    progress.assert_called_with(32, 32)


@pytest.mark.parametrize("data", [TRAVERSAL, SYMLINK, VALID[:40]])
def test_7z_rejects_unsafe_or_corrupt_archives(tmp_path, data):
    archive = tmp_path / "payload.zip.tmp"
    archive.write_bytes(data)
    dest = tmp_path / "owned"
    with pytest.raises(ValueError):
        DownloadFileAdapter().extract_zip(str(archive), str(dest), str(tmp_path))
    assert not (tmp_path / "escape.iso").exists()


def test_7z_never_overwrites_files_or_follows_existing_symlinks(tmp_path):
    archive = tmp_path / "payload.zip.tmp"
    archive.write_bytes(VALID)
    dest = tmp_path / "owned"
    dest.mkdir()
    target = dest / "Homebrew.iso"
    target.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        DownloadFileAdapter().extract_zip(str(archive), str(dest), str(tmp_path))
    assert target.read_bytes() == b"keep"
    target.unlink()
    outside = tmp_path / "outside.iso"
    outside.write_bytes(b"keep")
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        DownloadFileAdapter().extract_zip(str(archive), str(dest), str(tmp_path))
    assert outside.read_bytes() == b"keep"
