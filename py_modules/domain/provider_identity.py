"""Disjoint local identity space; RomM IDs remain unchanged."""

PUBLIC_ID_START = 1 << 52
MAX_LOCAL_ID = (1 << 53) - 1


def is_public_id(rom_id: int) -> bool:
    return rom_id >= PUBLIC_ID_START
