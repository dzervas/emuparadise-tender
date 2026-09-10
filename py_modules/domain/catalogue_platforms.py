"""Explicit platform correspondence; never match games by title alone."""

# EmuParadise section, Romspedia/RomsDL section, ES-DE system.
PLATFORMS = (
    ("Nintendo_Game_Boy_ROMs", "gameboy", "gb"),
    ("Nintendo_Game_Boy_Color_ROMs", "gameboy-color", "gbc"),
    ("Nintendo_Gameboy_Advance_ROMs", "gameboy-advance", "gba"),
    ("Nintendo_Entertainment_System_ROMs", "nintendo", "nes"),
    ("Super_Nintendo_Entertainment_System_(SNES)_ROMs", "super-nintendo", "snes"),
    ("Nintendo_64_ROMs", "nintendo-64", "n64"),
    ("Nintendo_DS_ROMs", "nintendo-ds", "nds"),
    ("Nintendo_Gamecube_ISOs", "nintendo-gamecube", "gc"),
    ("Nintendo_Wii_ISOs", "nintendo-wii", "wii"),
    ("Sony_Playstation_ISOs", "playstation-1", "psx"),
    ("Sony_Playstation_2_ISOs", "playstation-2", "ps2"),
    ("PSP_ISOs", "playstation-portable", "psp"),
    ("Sega_Genesis_-_Sega_Megadrive_ROMs", "sega-genesis", "megadrive"),
    ("Sega_Dreamcast_ISOs", "sega-dreamcast", "dreamcast"),
)


def catalogue_system(section: str, download_section: str) -> str:
    for catalogue, download, system in PLATFORMS:
        if section == catalogue and download_section == download:
            return system
    raise ValueError("The catalogue and download platform do not match a supported system")
