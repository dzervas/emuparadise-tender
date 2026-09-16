# EmuParadise Tender

A Decky Loader plugin for finding games in EmuParadise's catalogue and installing available public downloads into RetroDECK or EmuDeck from Steam Deck Game Mode.

- **Search:** full-width artwork grid, Enter-to-search, and an optional platform filter. Includes all supported game results from EmuParadise's default response; no background catalogue pagination.
- **Download choices:** a native Decky modal shows providers, regions, archive formats and sizes. Providers are Romspedia, RomsDL and Vimm's Lair.
- **Downloads:** queue status, progress and cancellation.
- **Installation & installed games:** choose your emulator setup, delete recorded ROMs, and run Steam ROM Manager for EmuDeck.
- **Download latest Tender:** checks this fork's latest GitHub release and saves `Tender.zip` into your user's `Downloads` directory. Install the ZIP manually through Decky's developer settings.

RomM accounts, server connections, library synchronisation, cloud saves and achievements have been removed. Existing local installation records and saves are retained. Historical database/folder names remain for upgrade compatibility.

## Installation

Install the latest `Tender.zip` from [this fork's releases](https://github.com/dzervas/emuparadise-tender/releases). Configure RetroDECK or EmuDeck first, then choose the installation in Search → Installation & installed games. Restart Decky after changing it.

RetroDECK shortcuts are managed by Tender. EmuDeck uses configured Steam ROM Manager parsers; update the Steam library after downloads finish. That action runs enabled SRM parsers and restarts Game Mode after explicit confirmation. Close running games first.

Only download content you are authorised to use. Tender uses published provider flows and does not bypass unavailable downloads or human verification. Vimm currently returns a human-verification challenge for some game pages; these are reported as unavailable while other providers remain usable. PS3 and Switch are selectable, but EmuParadise has no supported catalogue for them, so those filters return an explicit empty result.

## Development

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
python3 scripts/build_plugin_archive.py /tmp/Tender.zip
```

Python tests use pytest, pytest-asyncio and hypothesis. The test suite includes public-provider fixtures, a real SQLite/ZIP install-and-delete flow, and frozen-Decky import checks. Live Steam controller focus, emulator launching and source availability still need device testing.

The documentation tree retains upstream architectural history. The current workflow is described in [Search and installation](docs/user-guide/catalogue-imports.md).

Based on [danielcopper/romm-tender](https://github.com/danielcopper/romm-tender), licensed under GPL-3.0.
