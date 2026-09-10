"""Durable catalogue-to-local identity mapping, independent of installed bytes."""

import json
import sqlite3
from contextlib import closing
from typing import Any

from domain.provider_identity import MAX_LOCAL_ID, PUBLIC_ID_START


class PublicSourceStore:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    def get(self, rom_id: int) -> dict[str, Any] | None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(
                "SELECT detail_json, download_provider, download_page FROM public_sources WHERE rom_id = ?", (rom_id,)
            ).fetchone()
        if row is None:
            return None
        return {"detail": json.loads(row[0]), "download_provider": row[1], "download_page": row[2]}

    def register(self, catalogue: str, external_id: str, detail: dict[str, Any], provider: str, page: str) -> int:
        with closing(sqlite3.connect(self._db_path, timeout=5)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT rom_id, download_provider, download_page FROM public_sources "
                "WHERE catalogue = ? AND external_id = ?",
                (catalogue, external_id),
            ).fetchone()
            if existing:
                if (provider, page) != (existing[1], existing[2]):
                    raise ValueError("This catalogue item is already bound to a different download source")
                return existing[0]
            maximum = conn.execute("SELECT MAX(rom_id) FROM public_sources").fetchone()[0]
            rom_id = max(PUBLIC_ID_START, (maximum or 0) + 1)
            while conn.execute("SELECT 1 FROM roms WHERE rom_id = ?", (rom_id,)).fetchone():
                rom_id += 1
            if rom_id > MAX_LOCAL_ID:
                raise ValueError("The local catalogue identity space is exhausted")
            detail = {**detail, "id": rom_id}
            conn.execute(
                "INSERT INTO public_sources VALUES (?, ?, ?, ?, ?, ?)",
                (rom_id, catalogue, external_id, json.dumps(detail), provider, page),
            )
            return rom_id
