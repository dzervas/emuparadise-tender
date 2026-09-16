# Search and installation

Open **Search** in Tender. Choose Any or a platform, type a title, and press Enter or Search EmuParadise. Tender reads one default EmuParadise results page and preserves every supported game result. Artwork loads from the catalogue entry pages with bounded concurrency and a session cache; unavailable artwork has a placeholder. Platform badges remain visible independently of the cover.

Select a game to open the native Decky download dialog. All three providers are searched automatically with the game's platform. Each option shows its provider, region, archive format, size and filename. A provider failure is shown in the dialog without discarding working alternatives. Select an option to queue the download, then use Downloads for progress and cancellation.

The filter offers PS3, PS2, PS1, PSP, GC, GB, GBC, GBA, Switch and Wii. Unsupported catalogue systems, currently PS3 and Switch, return no games rather than silently searching other platforms. Download availability depends on the selected source. Vimm uses its published download form and archive metadata; a human-verification challenge or withdrawn download remains unavailable.

Use **Installation & installed games** to choose Auto, RetroDECK or EmuDeck. Save and restart Decky before installing after a selection change. Recorded games can be deleted here; Tender keeps saves and unrelated files. For EmuDeck, use Update Steam library and restart after downloads finish. This runs enabled SRM parsers, not just Tender's games, and requires confirmation with no running game.

**Download latest Tender** on the home page saves the latest release's `Tender.zip` to Downloads for manual developer installation. The file is downloaded to a temporary path, validated, then atomically replaces the previous ZIP. Failed downloads leave the previous package intact.

The public-only fork does not connect to RomM or synchronise libraries, saves, playtime or achievements. Existing local records continue to use their original data directories; removing the server functionality does not delete saved games.
