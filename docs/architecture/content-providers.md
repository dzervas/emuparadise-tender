# Content providers and emulator installations

Status: proposed, before implementation. Inspected upstream commit
`54494b5faa1732ba593751ff0062d9df362e98d3` (Tender 0.32.0).

## Existing architecture

| Boundary | Current owner | Constraint for this refactor |
| --- | --- | --- |
| Decky lifecycle and frontend callables | `main.py` | Keep existing wire contracts compatible |
| Concrete adapter construction | `bootstrap/adapters.py` | Construct providers and installation adapters here |
| Service composition | `bootstrap/services.py` | Inject protocols into services |
| RomM HTTP, authentication and retries | `adapters/romm/` | Preserve token-origin binding and error translation |
| Platform, collection and ROM fetch | `services/library/fetcher.py` | Separate catalogue reads from RomM extensions |
| Preview, incremental apply and acknowledgements | `services/library/` | Reuse bounded Steam event/acknowledgement pipeline |
| Download, extraction and install recording | `services/downloads.py`, `services/rom_install_recorder.py` | Reuse occupancy, cancellation and path checks |
| Installed-file deletion | `services/rom_removal.py`, `adapters/rom_files.py` | Require recorded ownership and guarded paths |
| Steam shortcuts, artwork and controller UI | `src/`, Steam adapters | Preserve Steam-assigned app IDs and Game Mode focus |
| Emulator resolution | `adapters/atlas_catalogue.py`, `services/active_core_resolver.py` | Keep one consistent selected installation |
| Root directories | `adapters/retrodeck_paths.py` | Currently only reads RetroDECK configuration |
| Launch command rendering | `domain/shortcut_data.py` | Currently hardcodes RetroDECK's Flatpak launch contract |

SQLite's `roms` row is the identity anchor for installs, cached metadata, saves,
playtime and Steam bindings. Uninstall removes installed bytes and the install row;
it deliberately retains saves, playtime and the shortcut. Removing a Steam shortcut
is a separate operation. Provider identity must therefore survive catalogue refresh,
disconnect, restart and uninstall.

## Proposed provider boundary

Separate content source from emulator installation. RomM and EmuParadise describe
content; EmuDeck and RetroDECK determine where it belongs and how it launches.

Introduce small protocol surfaces for catalogue browsing, item detail, download
resolution/transfer and cover retrieval. Providers return normalized item data and
explicit availability, not HTML disguised as a ROM or fabricated filenames. Keep
collections and timestamp-based incremental fetch as optional capabilities. Do not
make a new provider emulate RomM authentication, save sync, firmware, devices,
playtime ingest or destructive entity-liveness proofs.

Retain the current RomM adapter and its HTTP behavior. Route shared content reads
through the new boundary, with an explicit registry selecting the correct source.
Existing RomM integer IDs must remain stable. Persist a mapping from provider
instance plus external ID to local identity for new sources; never hash external
IDs into an unchecked collision space. Platform stamps, sibling groups, artwork,
download queues and retained rows must share that namespace. RomM-only operations
must not receive another provider's local IDs.

Add an on-demand catalogue browser to the existing controller-friendly UI. Do not
bulk-sync a public catalogue's thousands of entries into Steam. A selected item uses
the existing install and shortcut pipeline. Unavailable items remain browsable but
cannot create a misleading installable shortcut.

## EmuParadise observations and unresolved download contract

Inspected the public site on 2026-09-10. The
[catalogue index](https://www.emuparadise.me/roms-isos-games.php) states that game
download links were removed. Individual game pages nevertheless expose links
labelled Download. Following the visible link on the
[Tetris catalogue page](https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Tetris_%28World%29/69822)
reaches a
[download page](https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Tetris_%28World%29/69822-download)
that says the game is unavailable. This proves neither that every item is unavailable
nor that every Download link returns game bytes.

A working public download example remains necessary to verify the final link,
response type, archive format, filename, redirects and resume behavior. Follow only
published download paths for authorized content. Do not reconstruct retired endpoints
or infer availability from a link label. Separate browsing availability, file
availability and distribution authorization; public visibility alone is not a license.
No runtime implementation has been made while that contract remains unverified.

## EmuDeck and RetroDECK

RetroDECK bundles emulators in one Flatpak. EmuDeck configures separate emulators
and launchers. They are not interchangeable launch targets.

The vendored Atlas resolver already detects both, but Tender's integration is
incomplete for EmuDeck: its directory adapter reads only RetroDECK configuration,
and the command renderer emits `flatpak run net.retrodeck.retrodeck`, even though
the catalogue adapter may have selected EmuDeck. Detection alone is not support.

Use explicit installation selection if both exist. Derive ROM and BIOS roots from
that installation's configuration, including SD-card paths and symlinks. EmuDeck's
`~/.config/EmuDeck/settings.sh` must be parsed as data, never sourced as shell code.
Validate the chosen system's directory against the effective frontend configuration;
do not assume every system slug equals its directory name. The same installation
must drive downloads, launcher resolution, artwork references and deletion guards.
Changing installations cannot silently reclassify existing installed paths.

Preserve RetroDECK's launcher behavior. Add EmuDeck command resolution using its
installed launchers/emulators and argument-safe quoting. Do not substitute a guessed
Flatpak ID or fall back to RetroDECK when EmuDeck resolution fails. Unsupported
systems should explain the missing configuration before files are installed.

## Installation and deletion acceptance criteria

- Download into the configured system folder, including paths containing spaces.
- Keep incomplete downloads separate from complete files; honor pause/cancel.
- Reject traversal, unsafe archive members, symlink escapes and shared-folder deletion.
- Refuse overwrite of unowned content; retain the existing explicit adoption flow.
- Record the installed file or dedicated game directory before offering uninstall.
- Delete only the recorded installation; retain saves, BIOS and unrelated games.
- Preserve the ownership record when deletion fails or its outcome is ambiguous.
- Keep enough installation identity to uninstall after restart or provider removal.
- Verify Steam shortcut creation and deletion are distinct from ROM uninstall.

## Validation and delivery

Use logical commits: this design, release-only CI, the provider seam preserving RomM,
EmuParadise integration, and EmuDeck support with focused regression tests. Keep
upstream tests and architecture tools available locally. Review deficiencies along
these touched paths against evidence; avoid unrelated rewrites based on assumptions
about how the original project was authored.

The fork's CI is manually dispatched for releases only: build/package Tender and
attach the installable ZIP to a draft release. Pushes and PRs do not trigger it.
Remove release-please, SonarCloud, Pages publishing and issue/PR automation.
No external service secrets should be required. Keep packaging checks for the Python
backend, migrations, vendored resolver/native library and executable launcher.

Run provider fixture tests, RomM compatibility tests, filesystem install/uninstall
tests, frontend type checking and the frontend build locally during implementation.
Real Steam/Decky controller focus and emulator launch behavior require a Steam Deck;
a successful Rollup build is not evidence those device behaviors were tested.
