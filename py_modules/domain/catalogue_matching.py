"""Conservative title matching across catalogues; platforms must match separately."""

import re
import unicodedata


def base_title(title: str) -> str:
    title = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", title)
    title = re.sub(r"(?:\s+(?:ROMs?|ISOs?))+\s*$", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip()


def title_key(title: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", base_title(title)).casefold() if character.isalnum()
    )


_REGION_NAMES = {
    "e": "Europe",
    "eu": "Europe",
    "europe": "Europe",
    "pal": "PAL",
    "u": "USA",
    "us": "USA",
    "usa": "USA",
    "ntsc-u": "USA",
    "j": "Japan",
    "jp": "Japan",
    "japan": "Japan",
    "ntsc-j": "Japan",
    "w": "World",
    "world": "World",
    "a": "Australia",
    "australia": "Australia",
    "k": "Korea",
    "korea": "Korea",
    "asia": "Asia",
    "china": "China",
    "taiwan": "Taiwan",
    "brazil": "Brazil",
    "canada": "Canada",
    "france": "France",
    "germany": "Germany",
    "italy": "Italy",
    "spain": "Spain",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
}


def download_region(filename: str) -> str | None:
    """Label only region tags published in the source filename, not catalogue metadata."""
    regions = []
    for group in re.findall(r"\(([^)]*)\)|\[([^]]*)\]", filename):
        for part in re.split(r"[,/]", group[0] or group[1]):
            region = _REGION_NAMES.get(part.strip().casefold())
            if region and region not in regions:
                regions.append(region)
    return ", ".join(regions) or None
