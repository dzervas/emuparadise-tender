# Catalogue imports in this fork

Open **Tender → Catalogue** in Game Mode. RomM is optional for this workflow.

1. Choose the emulator installation first. Auto prefers RetroDECK when both are
   detected. Save an explicit choice and restart Decky before importing games.
2. Enter an EmuParadise game catalogue URL and select Romspedia or RomsDL.
3. Enter that download provider's game page URL. Use its game page, not an
   advertisement, direct file URL or countdown page.
4. Inspect the entry. Check the game title, platform, region and revision against
   the displayed archive filename; the plugin does not guess cross-site matches.
5. Import the entry, then download it. For RetroDECK, Tender creates the Steam
   shortcut and applies available catalogue artwork. For EmuDeck, SRM owns shortcuts;
   follow the update-and-restart flow below.

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

EmuDeck downloads no longer require readable ES-DE emulator command declarations.
The configured EmuDeck and ES-DE ROM roots must agree, and the system directory must
already exist inside that root. Escaping symlinks and divergent custom roots are
refused. SRM's configured parsers choose the launchers and artwork. Public catalogue
games use local saves; EmuDeck save-sync layouts have not been validated.

## EmuDeck: update Steam from Game Mode (experimental)

The Catalogue page has a persistent **EmuDeck library** list. Select an imported game
there to download or delete its files after reopening the plugin. RomM games can also
be imported by their numeric ROM ID; the existing bulk shortcut sync is reserved for
RetroDECK so it cannot create competing EmuDeck shortcuts.

After downloads finish, close running games and choose **Update Steam library and
restart**, then confirm. The action runs **all enabled SRM parsers**, including games
outside Tender. Game Mode temporarily closes while SRM writes, then the same Game
Mode session is started again. Use **Refresh library and SRM status** to read the
persisted outcome after reconnecting. This is a session restart, not a device reboot.

The first implementation supports active user services `gamescope-session.service`
and `gamescope-session-plus@steam.service`. It requires systemd, a system Python 3,
`runuser`, `pgrep`, `xvfb-run`, `Xvfb`, and `xauth`, plus an already configured EmuDeck
SRM AppImage. These dependencies are checked without stopping Steam. They are **not
assumed to exist on stock SteamOS**. An unsupported session or missing dependency is
reported in the panel; Tender does not install OS packages or alter session services.
Device validation is still required, including user-manager survival and returning
to the correct display. Do not enable this flow during a game or another SRM session.

A detached system service runs as the Steam user with a PAM login session. It stops
the detected Game Mode user service, verifies that Steam exited, runs SRM under a
private X display with a 15-minute timeout, and attempts session recovery on either
success or failure. Logs are stored in `srm/status.log` and the result in
`srm/status.json` under Tender's data directory. A reported CLI completion does not
prove every game matched a parser: inspect the resulting Steam library.

Deleting ROM files preserves saves. Run the update again afterward. SRM can leave a
stale shortcut when a parser produces no games; that shortcut may need removal in
SRM. Tender never invokes SRM's broad `remove` or `nuke` commands. Existing
Tender-owned shortcut bindings must be removed before handing an older EmuDeck
library to SRM; automatic ownership migration is not implemented.

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

The workflow is manual: select patch, minor, or major. It bumps `package.json`,
builds the ZIP, then atomically pushes the version commit and `v` tag and publishes
a normal GitHub release with generated notes. Release from `main` only. Pushes and
pull requests do not run CI. Steam/Decky controller behavior and real emulator launches
still require a device check before publishing a release.
