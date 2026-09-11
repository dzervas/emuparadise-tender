"""Stream 7z entries through system libarchive into an owned ROM directory."""

from __future__ import annotations

import ctypes
import os
import stat
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

MAGIC = b"7z\xbc\xaf\x27\x1c"


def _library():
    # SteamOS's system library; no optional Python packages or downloaded executables.
    try:
        lib = ctypes.CDLL("libarchive.so.13")
    except OSError as exc:
        raise ValueError("7z extraction needs the system libarchive.so.13 library") from exc
    pointer = ctypes.c_void_p
    signatures = {
        "archive_read_new": (pointer, []),
        "archive_read_support_format_7zip": (ctypes.c_int, [pointer]),
        "archive_read_open_filename": (ctypes.c_int, [pointer, ctypes.c_char_p, ctypes.c_size_t]),
        "archive_read_next_header": (ctypes.c_int, [pointer, ctypes.POINTER(pointer)]),
        "archive_read_data": (ctypes.c_ssize_t, [pointer, pointer, ctypes.c_size_t]),
        "archive_read_free": (ctypes.c_int, [pointer]),
        "archive_error_string": (ctypes.c_char_p, [pointer]),
        "archive_entry_pathname": (ctypes.c_char_p, [pointer]),
        "archive_entry_filetype": (ctypes.c_uint, [pointer]),
        "archive_entry_size": (ctypes.c_int64, [pointer]),
        "archive_entry_symlink": (ctypes.c_char_p, [pointer]),
        "archive_entry_hardlink": (ctypes.c_char_p, [pointer]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(lib, name)
        function.restype = result
        function.argtypes = arguments
    return lib


def ensure_7z_available() -> None:
    """Fail during source discovery rather than after a large download."""
    _library()


def _target(root: str, name: str) -> str:
    if not name or os.path.isabs(name) or "\\" in name or ".." in name.split("/"):
        raise ValueError(f"Unsafe 7z member path: {name!r}")
    target = os.path.join(root, name)
    resolved = os.path.realpath(target)
    if not resolved.startswith(root + os.sep):
        raise ValueError(f"7z member would extract outside target directory: {name!r}")
    current = root
    for part in name.split("/"):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise ValueError(f"7z member crosses a symbolic link: {name!r}")
    return target


def extract_7z(
    archive_path: str, dest_dir: str, safe_root: str, *, progress_callback: Callable[[int, int], None] | None = None
) -> None:
    root, safe = os.path.realpath(dest_dir), os.path.realpath(safe_root)
    if not root.startswith(safe + os.sep):
        raise ValueError("7z extraction requires an owned directory below the ROM root")
    lib = _library()
    handle = lib.archive_read_new()
    if not handle:
        raise MemoryError("Could not allocate 7z reader")

    def check(result):
        if result < 0:
            error = lib.archive_error_string(handle)
            raise ValueError("7z extraction failed: " + (error.decode(errors="replace") if error else str(result)))

    extracted = 0
    try:
        check(lib.archive_read_support_format_7zip(handle))
        check(lib.archive_read_open_filename(handle, os.fsencode(archive_path), 256 * 1024))
        entry = ctypes.c_void_p()
        buffer = ctypes.create_string_buffer(256 * 1024)
        while True:
            result = lib.archive_read_next_header(handle, ctypes.byref(entry))
            if result == 1:  # ARCHIVE_EOF
                break
            check(result)
            name = lib.archive_entry_pathname(entry)
            if name is None:
                raise ValueError("7z member has no filename")
            target = _target(root, os.fsdecode(name))
            kind = lib.archive_entry_filetype(entry)
            if (
                lib.archive_entry_symlink(entry)
                or lib.archive_entry_hardlink(entry)
                or kind not in (stat.S_IFREG, stat.S_IFDIR)
            ):
                raise ValueError("7z links and special files are not supported")
            if kind == stat.S_IFDIR:
                os.makedirs(target, exist_ok=True)
                continue
            size = lib.archive_entry_size(entry)
            if size < 0:
                raise ValueError("7z member has an invalid size")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            # Never overwrite another file or follow a pre-existing symlink.
            with open(target, "xb") as output:
                written = 0
                while True:
                    count = lib.archive_read_data(handle, buffer, len(buffer))
                    check(count)
                    if count == 0:
                        break
                    output.write(buffer.raw[:count])
                    written += count
                    extracted += count
                    if progress_callback is not None:
                        progress_callback(extracted, 0)  # Solid archives do not expose the full total up front.
                if written != size:
                    raise ValueError("7z member is incomplete")
        if progress_callback is not None:
            progress_callback(extracted, extracted)
    finally:
        lib.archive_read_free(handle)
