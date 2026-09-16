"""Download the latest published Tender package for manual Decky installation."""

import json
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from adapters.public_catalogue.http import PublicHttpAdapter, PublicSourceError, _system_ssl_context

REPOSITORY = "dzervas/emuparadise-tender"


def download_latest_release(user_home: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Tender"},
    )
    with urllib.request.urlopen(request, timeout=30, context=_system_ssl_context()) as response:
        release = json.loads(response.read(2_000_000))
    assets = [asset for asset in release.get("assets", []) if asset.get("name") == "Tender.zip"]
    if len(assets) != 1:
        raise PublicSourceError("The latest release does not contain Tender.zip")
    url = assets[0]["browser_download_url"]
    if not url.startswith(f"https://github.com/{REPOSITORY}/releases/download/"):
        raise PublicSourceError("Unexpected release asset URL")
    directory = Path(user_home) / "Downloads"
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".Tender-", suffix=".zip", dir=directory)
    os.close(fd)
    try:
        PublicHttpAdapter(
            hosts=frozenset({"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}),
            user_agent="Tender",
        ).download_zip(url, temporary)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or "Tender/plugin.json" not in archive.namelist():
                raise PublicSourceError("The release is not a valid Tender plugin package")
        os.replace(temporary, directory / "Tender.zip")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {
        "success": True,
        "message": (
            f"{release['tag_name']} saved to {directory / 'Tender.zip'}. Install it through Decky's developer settings."
        ),
    }
