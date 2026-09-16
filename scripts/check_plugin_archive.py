"""Validate the Decky build output before publishing an installable artifact."""

import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


def validate_archive(archive: Path) -> None:
    required = {
        "main.py",
        "plugin.json",
        "package.json",
        "dist/index.js",
        "bin/rom-launcher",
        "config.json",
        "py_modules/bootstrap/__init__.py",
        "py_modules/db/migrations/001_initial.sql",
        "py_modules/_vendor/atlas/__init__.py",
        "py_modules/_vendor/atlas/data/system_ids.json",
    }
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        paths = [PurePosixPath(name) for name in names]
        if any(path.is_absolute() or ".." in path.parts for path in paths):
            raise ValueError("Unsafe archive path")
        roots = {path.parts[0] for path in paths if path.parts}
        if len(roots) != 1:
            raise ValueError("Expected one plugin directory at the archive root")
        root = roots.pop()
        members = {str(path.relative_to(root)) for path in paths}
        missing = required - members
        if missing:
            raise ValueError(f"Missing required entries: {sorted(missing)}")
        if any(path.suffix == ".map" for path in paths):
            raise ValueError("Production archive contains source maps")
        for name in required:
            info = bundle.getinfo(f"{root}/{name}")
            if not info.file_size or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Missing payload or symlink at {name}")
        launcher_mode = bundle.getinfo(f"{root}/bin/rom-launcher").external_attr >> 16
        if not launcher_mode & 0o111:
            raise ValueError("ROM launcher is not executable")
        metadata = json.loads(bundle.read(f"{root}/plugin.json"))
        if metadata.get("name") != "Tender":
            raise ValueError("Archive must identify itself as Tender for Decky updates")
        bad_member = bundle.testzip()
        if bad_member:
            raise ValueError(f"Archive CRC failure: {bad_member}")


def main() -> None:
    output_dir, destination = map(Path, sys.argv[1:])
    archives = list(output_dir.glob("*.zip"))
    if len(archives) != 1:
        raise ValueError(f"Expected exactly one build ZIP, found {len(archives)}")
    validate_archive(archives[0])
    shutil.copyfile(archives[0], destination)
    print(f"Validated {destination.name}")


if __name__ == "__main__":
    main()
