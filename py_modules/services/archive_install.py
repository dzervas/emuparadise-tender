"""Single-file public archive placement with file-scoped install ownership."""

import os
from typing import Any

from domain.provider_identity import is_public_id
from services.protocols import DownloadFileStore, RomInstallRecorder


def record_single_archive(
    store: DownloadFileStore,
    recorder: RomInstallRecorder,
    extract_dir: str,
    rom_id: int,
    detail: dict[str, Any],
    system: str,
) -> tuple[str | None, str | None] | None:
    if not is_public_id(rom_id):
        return None
    files = store.scan_files_with_sizes(extract_dir)
    if len(files) != 1:
        return None
    source = files[0][0]
    destination = os.path.join(os.path.dirname(extract_dir), os.path.basename(source))
    store.publish_file(source, destination)
    try:
        store.remove_tree(extract_dir)
        return recorder.do_record_install(
            rom_id=rom_id,
            rom_detail=detail,
            file_path=destination,
            rom_dir=None,
            system=system,
            cleanup=lambda: store.remove_file(destination),
        )
    except Exception:
        store.remove_file(destination)
        raise


def archive_cleanup_dirs(target: str, stage_name: str, final: str | None) -> set[str]:
    """Never grant directory ownership to the shared parent of a flat install."""
    platform = os.path.dirname(target)
    directories = {os.path.join(platform, stage_name)}
    if final and os.path.dirname(final) != platform:
        directories.add(os.path.dirname(final))
    return directories
