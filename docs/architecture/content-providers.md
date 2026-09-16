# Public content providers

`bootstrap/__init__.py` composes the public catalogue, local source store, download/install engine and ROM removal service. It does not construct server adapters or save-sync services.

EmuParadise provides metadata and platform-filtered search. The adapter sends the published `section=roms` and `sysid` parameters, validates returned platform sections, and never follows catalogue pagination. Entry artwork is fetched separately, with at most four concurrent backend requests and a bounded session cache.

Romspedia, RomsDL and Vimm resolve public download flows. Provider search uses the selected entry's platform; import validates that the resolved archive is for the same platform. Vimm reads the published `dl_form`, gets the archive filename using HEAD, and supplies the Vault page as Referer on download. Human verification is surfaced, not submitted or bypassed.

`ContentApiRouter` reads only locally registered public IDs. It has no server delegate or dynamic extension mechanism. Historical schema and data-directory names are retained so existing installations remain addressable.

The shared archive installer retains staged extraction, flat single-file publication, path validation and recorded ownership for deletion. The public download admission gate refuses occupied untracked paths. Steam ROM Manager remains the shortcut owner for EmuDeck; Tender creates and updates RetroDECK shortcuts.

`release.py` reads this fork's latest GitHub release and downloads only its `Tender.zip` asset. ZIP validation and atomic replacement protect the previous package if a transfer fails. Installation is manual.
