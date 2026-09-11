# Content providers and emulator installations

Status: implemented in this fork; Steam Deck validation remains outstanding.
The original proposal preceded code changes and inspected upstream commit
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

## Implemented provider boundary

Separate content source from emulator installation. RomM and EmuParadise describe
content; EmuDeck and RetroDECK determine where it belongs and how it launches.

Use small protocol surfaces for catalogue browsing, item detail, download
resolution/transfer and cover retrieval. Providers return normalized item data and
explicit availability, not HTML disguised as a ROM or fabricated filenames. Keep
collections and timestamp-based incremental fetch as optional capabilities. Do not
make a new provider emulate RomM authentication, save sync, firmware, devices,
playtime ingest or destructive entity-liveness proofs.

Retain the current RomM adapter and its HTTP behavior. Route shared content reads
through `ContentApiRouter`, which retains the existing RomM adapter and delegates
its extensions while refusing public IDs in RomM-only operations.
Existing RomM integer IDs must remain stable. Persist `public_sources` mappings from catalogue plus external ID to local identity.
New IDs are allocated monotonically in `2^52 .. 2^53-1`, inside JavaScript's exact
integer range. Allocation checks existing ROM rows; RomM list responses using the
reserved range are refused. IDs are never hashed. Platform stamps, sibling groups, artwork,
download queues and retained rows must share that namespace. RomM-only operations
must not receive another provider's local IDs.

The controller-friendly Catalogue page imports one game at a time from explicit
EmuParadise and download-provider game URLs. Inspection shows the title, platform
and archive filename before import. This first version has no in-plugin site search
or bulk catalogue sync. Public imports use the existing install and Steam shortcut
pipeline, including artwork and Game Mode download/uninstall controls. RomM
connectivity and save-sync gates do not block public games.

## Catalogue and download sources

Inspected the public site on 2026-09-10. The
[catalogue index](https://www.emuparadise.me/roms-isos-games.php) states that game
download links were removed. Individual game pages nevertheless expose links
labelled Download. Following the visible link on the
[Tetris catalogue page](https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Tetris_%28World%29/69822)
reaches a
[download page](https://www.emuparadise.me/Nintendo_Game_Boy_ROMs/Tetris_%28World%29/69822-download)
that says the game is unavailable. This proves neither that every item is unavailable
nor that every Download link returns game bytes.

The catalogue and download provider are independent choices. EmuParadise supplies
metadata only. RomM retains its authenticated catalogue and byte transfer adapter;
Romspedia and RomsDL resolve files from their public game pages. A selected source
page is explicit: do not silently match titles across systems, revisions or regions.
Catalogue identity survives changing the selected download source.

Inspected public HTML on 2026-09-10: Romspedia's game page exposes a slow-download
link, whose landing page publishes a direct HTTPS file link. RomsDL's game page
publishes a POST download form with `rom_url`, `console_url` and a page-issued
`session` field. Read fresh form values, never manufacture a session or a URL.
Do not execute third-party JavaScript or follow advertisements. Source adapters must
reject login/challenge/error pages, unexpected redirect origins and ambiguous links.
A missing public path means unavailable, not permission to reconstruct an endpoint.

The byte-transfer boundary is separate from catalogue detail. The existing install
engine continues to own destination choice, occupancy checks, extraction, cancellation
and install records. A download adapter receives a destination chosen by that engine;
a remote filename never selects a local directory. Public HTTP uses its own transport
without RomM credentials, and its failures never constitute RomM deletion authority.
Resume requires a matching range response; HTML must never be installed as game bytes.
Only publicly distributed, authorized content belongs in this workflow. Visibility
and a site's cartridge-ownership disclaimer do not establish a distribution license.

## EmuDeck and RetroDECK

RetroDECK bundles emulators in one Flatpak. EmuDeck configures separate emulators
and launchers. They are not interchangeable launch targets.

The vendored Atlas resolver already detects both, but Tender's integration is
incomplete for EmuDeck: its directory adapter reads only RetroDECK configuration,
and the command renderer emits `flatpak run net.retrodeck.retrodeck`, even though
the catalogue adapter may have selected EmuDeck. Detection alone is not support.

The Catalogue page offers an installation choice. Auto prefers RetroDECK, then
EmuDeck. Explicit selections require a detected installation. Changing the choice
requires a restart and is refused while downloads, installed ROMs, BIOS records or
save tracking remain; new installations are blocked until that restart. The
migration service clears only empty-installation location markers when switching. Derive ROM and BIOS roots from
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

Use logical commits for the design, release-only CI, provider integration and
installation support, with focused regression tests. Keep
upstream tests and architecture tools available locally. Review deficiencies along
these touched paths against evidence; avoid unrelated rewrites based on assumptions
about how the original project was authored.

The fork's CI is manually dispatched for releases only: build/package Tender and
bump patch/minor/major, commit and tag the version, and publish the installable ZIP. Pushes and PRs do not trigger it.
Remove release-please, SonarCloud, Pages publishing and issue/PR automation.
No external service secrets should be required. Keep packaging checks for the Python
backend, migrations, vendored resolver/native library and executable launcher.

Run provider fixture tests, RomM compatibility tests, filesystem install/uninstall
tests, frontend type checking and the frontend build locally during implementation.
Real Steam/Decky controller focus and emulator launch behavior require a Steam Deck;
a successful Rollup build is not evidence those device behaviors were tested.

## Current boundaries and limitations

- `CatalogueReader` returns descriptive entries; `DownloadResolverReader` resolves
  a separately selected source page into an immutable `DownloadPlan`.
- `RomDetailReader` and `RomDownloadReader` are independently injected into the
  existing download engine. `RommRomReader` composes them for compatibility.
- Public entries retain their local ID across source changes. An uninstalled entry
  can select another provider/page; active downloads and installed copies prevent
  rebinding until cancelled/completed or deleted respectively.
- Public transfers support ZIP files, reject HTML and executable responses before
  opening the destination, detect incomplete transfers, and disable unverified
  range resume. Existing extraction and path-ownership checks still apply.
- EmuDeck uses SRM-owned shortcuts and the guarded Game Mode restart worker described
  below. Downloads require matching EmuDeck/ES-DE ROM roots and an existing system
  directory, but no longer require Tender to reconstruct emulator commands.
- RomM save sync remains specific to RomM content. Public games keep local playtime
  without queuing it for RomM, and retain local saves on uninstall. EmuDeck save-sync
  layouts are not validated by this change; RetroDECK's existing save integration
  remains the established path.
- Live checks resolved both sites' published download flows and EmuParadise metadata.
  Binary transfer and install/delete tests use synthetic archives, not commercial ROMs.

## Local validation (2026-09-10)

- Pinned pnpm 10.29.3 frozen installation, TypeScript check and Rollup build passed.
- Backend: 8,109 tests passed, one skipped; three Unix-socket filesystem tests were
  excluded after the environment denied socket creation. Five subtests also passed.
- Frontend: all 3,322 tests passed across 139 files.
- Ruff, basedpyright, import boundaries, callable parity, aggregate ownership,
  module-size and vendored-tree checks passed.
- The actual 360-file plugin ZIP passed the release packager's validation. The
  workflow itself was not enabled or dispatched, and no release was published.
- Runtime here was Python 3.12 and Node 24. Decky's Python 3.11, actual Steam input
  focus and emulator processes still need a Steam Deck check.


## EmuDeck SRM handoff

EmuDeck now assigns shortcut ownership to SRM; public imports remain unbound and
completed downloads skip Tender's launch-option bake. A persistent Catalogue list
owns file-management access. Explicit RomM-ID imports use the same unbound model;
legacy bulk shortcut sync is blocked for EmuDeck. RetroDECK behavior is unchanged.

The restart worker is detached from Decky using a system transient service running
as the Steam user. It controls only a recognized active Game Mode user service,
checks Steam has exited before the SRM write, isolates Electron with Xvfb, terminates
the writer process group on timeout, and attempts to restart the same session in a
finally block. Preflight refusals do not stop Steam. This boundary is deliberately
experimental pending hardware testing; exact prerequisites and recovery limitations
are in the catalogue user guide. SRM still owns parser selection, exclusions, matching,
artwork and its known empty-parser deletion behavior.


SRM follow-up validation: 119 focused backend checks and 6 frontend checks passed,
including unbound installation/deletion, preflight refusals, restart confirmation,
writer timeout cleanup, and session recovery failures. Frozen dependency installation,
frontend compilation, and the 362-file ZIP validation passed locally. No GitHub
workflow was dispatched and no real Steam session was stopped during these checks.


## Search-driven catalogue selection

The QAM Catalogue section replaces both URL fields with title search and a maximum
of five EmuParadise game/platform results. Selecting an entry queries the two download
providers independently. Adapters match normalized titles plus exact platform paths,
follow bounded published pagination, and resolve the existing public ZIP flows before
returning options. File size is provider metadata or unknown, never copied from a
different catalogue's file. The chosen option uses the existing import and download
pipeline, including durable source bindings and installation-specific shortcut ownership.
One provider's failure does not discard the other's results. No full-page browser,
new updater, or change to the release workflow is included in this follow-up.


## Frozen-runtime HTML dependency

Decky's Python bundle omits `html.parser`, so importing the catalogue adapter can
prevent the entire backend from loading. Keep the existing structural parser and
bundle CPython's pure-Python HTML package plus `_markupbase` under
`_vendor.cpython_html`, with relative internal imports, its license, provenance and
a checksum manifest. `PublicPage` changes only its parser import. No regex HTML
replacement or dependency on Decky's optional standard-library wrappers is needed.
Validate the complete bootstrap import and representative parsing in a fresh process
that refuses the absent standard-library modules; ordinary CPython tests alone did
not catch either this failure or the earlier `xml.etree` failure.


Validation against the module inventory of Decky's released v3.2.8 PluginLoader
confirmed that `html.parser`, `_markupbase`, and `xml.etree` are absent;
`unicodedata`, `http.cookiejar`, `urllib.request`, and `pyexpat` are present.
The regression test blocks all three absent modules while importing the complete
bootstrap and parsing entities, nested links, download forms and inert scripts.
This checks the known runtime gap without claiming a Steam Deck device test.


## Public-source TLS trust

The public-source opener must explicitly load the host's CA bundle: Decky's frozen
OpenSSL can use build-time default paths that do not resolve on SteamOS. Create a
verified default SSL context, then load the first existing OS trust bundle from
SteamOS/Arch and other common Linux locations. Pass that context to the opener's
HTTPS handler so both catalogue pages and ZIP transfers use the same trust policy.
Keep default trust paths when no known bundle exists. Never disable hostname or
certificate verification, download roots, or inherit RomM's insecure-SSL setting.
Log the selected system bundle to make device diagnosis possible.


## All-provider discovery and 7z downloads

The registry already dispatches every download resolver concurrently. Make that
observable with INFO start/result logs and one frontend outcome per registered
provider, including empty matches and failures. Keep working results when another
provider fails. Retain exact normalized title/year and platform matching; do not substitute
one year's game.

The reported PS2 titles publish `.7z` links, so extend public download validation
to ZIP and 7z signatures. Route 7z archives through a small adapter over the system
`libarchive.so.13`, loaded lazily; keep existing ZIP extraction unchanged. Stream
regular files into the existing owned installation directory and reuse launch-file
selection, installation recording and deletion. Reject traversal, links, special
files, collisions and corrupt archives. No downloaded native code, shell extraction,
provider bypasses or changes to SSL verification are required.


The 7z adapter binds the upstream [libarchive read API](https://github.com/libarchive/libarchive/blob/master/libarchive/archive.h)
and [entry API](https://github.com/libarchive/libarchive/blob/master/libarchive/archive_entry.h).
The system library name is listed in the [Arch libarchive package](https://archlinux.org/packages/core/x86_64/libarchive/files/).


## Download retries and library visibility

Some public file servers omit Content-Type for valid 7z files; urllib reports
`text/plain` for a missing header. Require a successful response and a supported
archive signature instead of rejecting an absent or generic MIME type. HTML or
other non-archive bytes still fail before the destination is opened.

Keep the catalogue's stable local ID, but permit replacing its download source
while uninstalled. Reject changes while a download is queued, paused or active,
while another guarded mutation is in flight, or while installed bytes remain.
Update the ROM filename and metadata when rebinding; never rewrite installed-file
ownership. Failed/uninstalled public entries stay available for identity reuse but
are omitted from the EmuDeck library list. RomM's explicit import-to-download flow
keeps its uninstalled entries visible.


## Game-level lookup and provider regions

Normalize catalogue metadata before removing a trailing ROM/ISO label, so
`Crash Bash (E) ISO[SCES-02834]` searches as `Crash Bash`. Match the normalized game
and the explicit platform independently of the selected catalogue region. Follow
published pagination within the existing six-page search budget and resolve every
matching variant found, rather than stopping at the first page or first two matches.
Expose region labels from the provider's published filename, never from the selected
EmuParadise entry; keep unknown regions explicit and the full filename visible.

### Single-file archive placement

Public catalogue archives with exactly one file are extracted privately, then published
directly in the platform ROM directory without replacing existing paths. Their install
record owns only that file. Multi-file archives retain dedicated directory ownership;
RomM placement and existing installations are unchanged. Failure cleanup must never
interpret a flat file’s parent (the shared platform directory) as an owned directory.
