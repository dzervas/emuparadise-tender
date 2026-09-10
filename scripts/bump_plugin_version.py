"""Advance the plugin version before building a release."""

import argparse
import json
import re
from pathlib import Path


def bump(version: str, level: str) -> str:
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Expected a stable major.minor.patch version")
    parts = list(map(int, version.split(".")))
    index = ("major", "minor", "patch").index(level)
    parts[index] += 1
    parts[index + 1:] = [0] * (2 - index)
    return ".".join(map(str, parts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=("patch", "minor", "major"))
    args = parser.parse_args()
    path = Path("package.json")
    data = json.loads(path.read_text())
    data["version"] = bump(data["version"], args.level)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print("v" + data["version"])
