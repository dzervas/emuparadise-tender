# Catalogue imports in this fork

Open **Tender → Catalogue** in Game Mode. RomM is optional for this workflow.

1. Choose the emulator installation first. Auto prefers RetroDECK when both are
   detected. Save an explicit choice and restart Decky before importing games.
2. Enter an EmuParadise game catalogue URL and select Romspedia or RomsDL.
3. Enter that download provider's game page URL. Use its game page, not an
   advertisement, direct file URL or countdown page.
4. Inspect the entry. Check the game title, platform, region and revision against
   the displayed archive filename; the plugin does not guess cross-site matches.
5. Import the entry, then download it. Tender creates the Steam shortcut using its
   existing Steam API integration and applies available catalogue artwork.

The Downloads page shows transfer progress and supports cancellation. The game’s
Steam page also provides Tender's download, play and uninstall controls. Public
sources currently use ZIP transfers without pause/resume; RomM retains its existing
resume behavior. Only use content you have permission to download.

**Delete installed ROM** removes the recorded game file or dedicated game directory.
It preserves other games, saves, BIOS files and the Steam shortcut. Removing the
shortcut is a separate operation. A failed download never becomes an installed ROM.
Re-importing the same catalogue entry preserves its identity and shortcut binding.
Its first download-source binding remains pinned; source switching is not yet exposed.

## Emulator paths

RetroDECK keeps its existing configured folders and launch commands. EmuDeck uses
its detected configuration and ES-DE's effective `ROMDirectory`, including a moved
SD-card root. The same selected installation supplies the download and deletion roots.
Installation changes are refused while managed ROMs, BIOS, save tracking or downloads
remain; this prevents a new root from making existing ownership records point elsewhere.

EmuDeck support currently requires readable ES-DE system declarations and installed
static launcher/core paths in `~/ES-DE/custom_systems/es_find_rules.xml`. A system
whose definition is sealed inside the AppImage, a missing launcher, an unsupported
placeholder or a custom system location is refused before installation. This release
does not automatically extract or replace ES-DE configuration. EmuDeck save-sync
layouts have not been validated; public catalogue games use local saves.

The current platform mappings cover GB, GBC, GBA, NES, SNES, N64, DS, GameCube, Wii,
PS1, PS2, PSP, Mega Drive and Dreamcast. Availability still depends on the installed
emulator, a matching source platform and a publicly published ZIP download.

## Build and release

Build with the pinned pnpm version from `package.json`:

```sh
pnpm install --frozen-lockfile
pnpm build
python3 scripts/build_plugin_archive.py dist/Tender.zip
```

The workflow is manual and creates a draft release with the plugin ZIP. Pushes and
pull requests do not run CI. Steam/Decky controller behavior and real emulator launches
still require a device check before publishing a release.
