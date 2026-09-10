import io
from email.message import Message
from http.client import HTTPMessage
from typing import cast
from unittest.mock import Mock
from urllib.request import Request

import pytest

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, _SourceRedirects


class Response(io.BytesIO):
    def __init__(self, body, content_type="application/zip", length=None):
        super().__init__(body)
        self.status = 200
        self.url = "https://downloads.romspedia.com/roms/Homebrew.zip"
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body) if length is None else length)


def client(response):
    adapter = PublicHttpAdapter(hosts=frozenset({"downloads.romspedia.com"}), user_agent="Tender-test")
    adapter._opener = Mock()
    adapter._opener.open.return_value = response
    return adapter


def test_transfer_reports_bytes_and_disables_unverified_resume(tmp_path):
    body = b"PK\x03\x04synthetic archive fixture"
    adapter = client(Response(body))
    target = tmp_path / "partial.tmp"
    progress, meta = Mock(), Mock()
    adapter.download_zip("https://downloads.romspedia.com/roms/Homebrew.zip", str(target), progress, on_meta=meta)
    assert target.read_bytes() == body
    meta.assert_called_once_with(False)
    progress.assert_called_with(len(body), len(body))
    request = cast("Mock", adapter._opener.open).call_args.args[0]
    assert request.get_header("Authorization") is None
    assert request.get_header("User-agent") == "Tender-test"


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"<html>captcha</html>", "text/html"),
        (b"<html>error</html>", "application/octet-stream"),
        (b'{"error":"no file"}', "application/json"),
        (b"MZexecutable", "application/octet-stream"),
    ],
)
def test_html_or_executable_never_overwrites_destination(tmp_path, body, content_type):
    adapter = client(Response(body, content_type))
    target = tmp_path / "partial.tmp"
    target.write_bytes(b"existing")
    with pytest.raises(PublicSourceError):
        adapter.download_zip("https://downloads.romspedia.com/roms/Homebrew.zip", str(target))
    assert target.read_bytes() == b"existing"


def test_incomplete_transfer_is_not_success(tmp_path):
    adapter = client(Response(b"PK\x03\x04short", length=100))
    with pytest.raises(PublicSourceError, match="incomplete"):
        adapter.download_zip("https://downloads.romspedia.com/roms/Homebrew.zip", str(tmp_path / "partial.tmp"))


def test_resume_refused_without_network_or_file_mutation(tmp_path):
    adapter = client(Response(b""))
    target = tmp_path / "partial.tmp"
    target.write_bytes(b"existing")
    with pytest.raises(PublicSourceError):
        adapter.download_zip("https://downloads.romspedia.com/roms/Homebrew.zip", str(target), resume=True)
    cast("Mock", adapter._opener.open).assert_not_called()
    assert target.read_bytes() == b"existing"


def test_redirect_checked_before_request_is_sent():
    handler = _SourceRedirects(frozenset({"downloads.romspedia.com"}))
    with pytest.raises(PublicSourceError):
        handler.redirect_request(
            Request("https://downloads.romspedia.com/a"),
            io.BytesIO(),
            302,
            "",
            HTTPMessage(),
            "https://localhost/secret",
        )
