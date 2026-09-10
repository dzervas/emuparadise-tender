"""Package Tender's compiled frontend and checked-in runtime for Decky Loader.

Runtime layout follows SteamDeckHomebrew/cli 0.0.8, zip_plugin/zip_path:
defaults are flattened into the plugin root. Development documentation in
defaults is excluded to avoid overwriting the plugin's README.
"""

import os
import stat
import sys
import zipfile
from pathlib import Path

from check_plugin_archive import validate_archive


def runtime_files(root: Path) -> list[tuple[Path, str]]:
    files = [(root / name, name) for name in ("LICENSE", "README.md", "main.py", "package.json", "plugin.json")]
    files.append((root / "dist/index.js", "dist/index.js"))
    for directory in ("bin", "py_modules", "defaults"):
        base = root / directory
        for path in sorted(base.rglob("*")):
            if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            if path.is_symlink():
                raise ValueError(f"Runtime payload cannot contain symlinks: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(f"Runtime payload must be a regular file: {path}")
            if directory == "defaults" and path.suffix == ".md":
                continue
            relative = path.relative_to(base if directory == "defaults" else root)
            files.append((path, relative.as_posix()))
    names = [name for _, name in files]
    if len(names) != len(set(names)):
        raise ValueError("Runtime files collide after flattening defaults")
    return files


def build_archive(root: Path, destination: Path) -> None:
    files = runtime_files(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
            for path, relative in files:
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"Missing regular runtime file: {path}")
                entry = zipfile.ZipInfo(f"Tender/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                permissions = 0o755 if path.stat().st_mode & 0o111 else 0o644
                entry.external_attr = (stat.S_IFREG | permissions) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, path.read_bytes(), compresslevel=9)
        validate_archive(temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Built and validated {destination} ({len(files)} files)")


if __name__ == "__main__":
    build_archive(Path(__file__).resolve().parents[1], Path(sys.argv[1]).resolve())
