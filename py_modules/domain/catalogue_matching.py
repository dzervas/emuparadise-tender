"""Conservative title matching across catalogues; platforms must match separately."""

import re
import unicodedata


def base_title(title: str) -> str:
    title = re.sub(r"\s+(?:ROMs?|ISOs?)\s*$", "", title, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)|\[[^]]*\]", "", title)).strip()


def title_key(title: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", base_title(title)).casefold() if character.isalnum()
    )
