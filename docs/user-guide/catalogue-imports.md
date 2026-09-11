# Catalogue imports in this fork

Open **Tender → Catalogue** in Game Mode. RomM is optional for this workflow.

1. Choose the emulator installation first. Auto prefers RetroDECK when both are
   detected. Save an explicit choice and restart Decky before importing games.
2. Enter a game title under **EmuParadise catalogue** and choose **Search EmuParadise**.
   The section shows at most five supported catalogue entries as **game – platform**.
3. Select a title to find matching Romspedia and RomsDL downloads. Searches match the
   normalized game title and exact platform; they do not promise identical regional
   revisions. Check the filename shown under each option.
4. Choose a **provider – region – ZIP/7Z – size** button to import and queue that download.
   A missing published file size is displayed as **Size unknown**. Unavailable
   providers are reported separately, so another provider can still be used.
5. RetroDECK gets Tender's existing Steam shortcut and available artwork. EmuDeck
   keeps SRM ownership; update its Steam library after the download finishes.

Only ordinary public search and download pages are used. Provider searches follow
at most six published search pages and resolve at most two matching files per
provider. Unsupported platforms, different titles, and unsupported archive formats are not
offered. No-match and source failures are displayed without inventing a download.

The Downloads page shows transfer progress and supports cancellation. The game’s
Steam page also provides Tender's download, play and uninstall controls. Public
sources currently use ZIP/7z transfers without pause/resume; RomM retains its existing
resume behavior. Only use content you have permission to download.

**Delete installed ROM** removes the recorded game file or dedicated game directory.
It preserves other games, saves, BIOS files and the Steam shortcut. Removing the
shortcut is a separate operation. A failed download never becomes an installed ROM.
Re-importing the same catalogue entry preserves its identity and shortcut binding.
An uninstalled game can switch download sources; its active download must finish or be cancelled first.

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
emulator, a matching source platform and a publicly published ZIP/7z download.

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


## Updating this fork

Install the new ZIP or its GitHub release asset URL again through Decky. The plugin
has no GitHub auto-updater. Decky's normal update list comes from its configured
plugin store and matches plugins by name. This fork still uses the name Tender, so
a store update can replace it with upstream Tender; use this fork's release assets
for now. A GitHub release alone does not register the fork with Decky's store.


## Catalogue errors and logs

Failed searches appear in red below Search EmuParadise. An unanswered backend call
stops waiting after 30 seconds (75 seconds for download-source discovery), so the
page allows another attempt. If the backend failed to start, it cannot return its
startup exception to the page; the message directs you to the logs instead.
Runtime catalogue failures retain their tracebacks in backend logs.

On a standard Steam Deck install, timestamped Tender logs are in
`/home/deck/homebrew/logs/Tender/`. Startup failures are also in the Decky journal:

```sh
sudo journalctl -u plugin_loader -b -n 150 --no-pager
sudo journalctl -u plugin_loader -f
```


The installation section shows the choice loaded by the backend, and save progress
or errors directly below Save. A successful change confirms the saved choice and
whether Decky must restart. Restarting only Steam does not necessarily reload
Tender's backend. Over SSH, `sudo systemctl restart plugin_loader` reloads Decky
and all its plugins. After reconnecting, check the loaded installation choice.
Installation loads and saves are logged at INFO; failed disk writes keep tracebacks.
An unconfirmed save instructs you to reload and verify the stored choice before retrying.


Public catalogue HTTPS and archive downloads use the system CA certificates with
certificate and hostname verification enabled. Tender logs the selected bundle
(e.g. `/etc/ssl/certs/ca-certificates.crt` on SteamOS) at startup. Missing OpenSSL
build-time paths do not prevent loading the OS bundle. If verification still fails,
the full error remains in the logs; no insecure retry is attempted.


Selecting a catalogue title searches every registered download provider automatically;
there is no provider selector before the search. Each provider then shows its option
count, no-match result, or error. All matching options appear together, labelled by
archive type, size and provider, with the published filename underneath. Check that
filename's region and language: a catalogue's European entry does not guarantee that
a download provider offers a European release.

ZIP and 7z downloads use the same installed-ROM tracking and deletion workflow.
7z extraction uses the host's `libarchive.so.13`; extraction rejects links, traversal,
special files and overwrites. It does not install tools or run archive contents.


After a failed download, select another provider's option for the same catalogue
game. Tender keeps its local identity and updates the source and filename. Finish
or cancel that game's active/paused download first; delete an installed copy before
switching sources. Failed or uninstalled public entries are hidden from the EmuDeck
library list; search again to retry. Installation records and save files are preserved.


Catalogue region tags and disc IDs are removed from provider search queries.
Choose among the providers' available regions explicitly; options label the region
from the published download filename, or show Unknown region. A selected catalogue
region does not filter out other source regions. Search follows up to six published
result pages and includes every matching variant found within that search budget.
