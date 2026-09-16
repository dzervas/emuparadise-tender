import json
import zipfile
from unittest.mock import Mock

import pytest

from adapters.public_catalogue import release


def setup_release(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps(
        {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "Tender.zip",
                    "browser_download_url": "https://github.com/dzervas/emuparadise-tender/releases/download/v1.2.3/Tender.zip",
                }
            ],
        }
    ).encode()
    monkeypatch.setattr(release.urllib.request, "urlopen", Mock(return_value=response))
    transport = Mock()
    monkeypatch.setattr(release, "PublicHttpAdapter", Mock(return_value=transport))
    return transport


def test_release_atomically_replaces_package(monkeypatch, tmp_path):
    transport = setup_release(monkeypatch)

    def download(url, dest):
        with zipfile.ZipFile(dest, "w") as archive:
            archive.writestr("Tender/plugin.json", '{"name":"Tender"}')

    transport.download_zip.side_effect = download
    result = release.download_latest_release(str(tmp_path))
    assert result["success"]
    assert zipfile.is_zipfile(tmp_path / "Downloads/Tender.zip")
    assert list((tmp_path / "Downloads").iterdir()) == [tmp_path / "Downloads/Tender.zip"]


def test_failed_release_keeps_existing_package(monkeypatch, tmp_path):
    transport = setup_release(monkeypatch)
    transport.download_zip.side_effect = OSError("transfer interrupted")
    directory = tmp_path / "Downloads"
    directory.mkdir()
    (directory / "Tender.zip").write_bytes(b"previous")
    with pytest.raises(OSError):
        release.download_latest_release(str(tmp_path))
    assert (directory / "Tender.zip").read_bytes() == b"previous"
    assert len(list(directory.iterdir())) == 1
