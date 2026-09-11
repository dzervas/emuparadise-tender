import { FC, useState, useEffect } from "react";
import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, TextField } from "@decky/ui";
import {
  getEmulatorInstallation,
  saveEmulatorInstallation,
  bindCatalogueShortcut,
  fetchCoverBase64,
  importCatalogueEntry,
  removeRom,
  startDownload,
  searchCatalogue,
  getCatalogueDownloads,
} from "../api/backend";
import type { CatalogueSearchItem, CatalogueDownloadOption } from "../api/backend";
import { addShortcut } from "../utils/steamShortcuts";
import { EmudeckLibrary } from "./EmudeckLibrary";
import { registerRomMAppId } from "../patches/gameDetailPatch";

function platformLabel(section: string): string {
  return section.replace(/_(?:ROMs|ISOs)$/, "").replace(/_/g, " ");
}

export const CataloguePage: FC<{ onBack: () => void }> = ({ onBack }) => {
  const [installation, setInstallation] = useState("auto");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogueSearchItem[]>([]);
  const [selected, setSelected] = useState<CatalogueSearchItem | null>(null);
  const [downloads, setDownloads] = useState<CatalogueDownloadOption[]>([]);
  const [romId, setRomId] = useState<number | null>(null);
  const [libraryRevision, setLibraryRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    void getEmulatorInstallation()
      .then((result) => setInstallation(result.selection))
      .catch((error) => setMessage(String(error)));
  }, []);
  const run = (action: () => Promise<void>) => {
    setBusy(true);
    void action()
      .catch((error) => setMessage(String(error)))
      .finally(() => setBusy(false));
  };
  const search = () =>
    run(async () => {
      setResults([]);
      setSelected(null);
      setDownloads([]);
      setRomId(null);
      setMessage("Searching EmuParadise…");
      const result = await searchCatalogue(query.trim());
      setResults(result.success ? result.items.slice(0, 5) : []);
      setMessage(
        result.success
          ? result.items.length
            ? ""
            : "No supported games found. Try a more specific title."
          : result.message || "Search failed",
      );
    });
  const choose = (item: CatalogueSearchItem) =>
    run(async () => {
      setSelected(item);
      setDownloads([]);
      setRomId(null);
      setMessage("Finding downloads…");
      const result = await getCatalogueDownloads(item.page_url);
      setDownloads(result.success ? result.items : []);
      setMessage(
        result.success
          ? [
              result.items.length
                ? "Check the filename's region and version before downloading."
                : "No matching public ZIP downloads found.",
              ...(result.messages || []),
            ].join(" ")
          : result.message || "Download sources unavailable",
      );
    });
  const download = (option: CatalogueDownloadOption) =>
    run(async () => {
      if (!selected) return;
      const result = await importCatalogueEntry(selected.page_url, option.provider, option.page_url);
      if (!result.success || !result.rom_id) throw new Error(result.message || "Import failed");
      if (result.shortcut_owner !== "srm") {
        let appId = result.app_id;
        if (!appId) {
          if (!result.shortcut) throw new Error("No shortcut data returned");
          appId = await addShortcut(result.shortcut);
          if (!appId) throw new Error("Steam could not create the shortcut");
          const bound = await bindCatalogueShortcut(result.rom_id, appId);
          if (!bound.success) {
            SteamClient.Apps.RemoveShortcut(appId);
            throw new Error(bound.message || "Steam shortcut could not be recorded");
          }
        }
        registerRomMAppId(appId);
        // Artwork availability must not prevent an otherwise valid download.
        try {
          const { base64 } = await fetchCoverBase64(result.rom_id);
          if (base64) await SteamClient.Apps.SetCustomArtworkForApp(appId, base64, "png", 0);
        } catch {
          /* The game remains usable without optional cover art. */
        }
      }
      setRomId(result.rom_id);
      setLibraryRevision((value) => value + 1);
      const queued = await startDownload(result.rom_id, false, null, null, false);
      setMessage(
        queued.success
          ? `Download queued. Progress is on Downloads.${result.shortcut_owner === "srm" ? " Update Steam library after it finishes." : ""}`
          : queued.message || "Download refused",
      );
    });
  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onBack}>
            Back
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Emulator installation">
        <PanelSectionRow>
          <DropdownItem
            label="Installation"
            selectedOption={installation}
            disabled={busy}
            rgOptions={[
              { label: "Auto (RetroDECK first)", data: "auto" },
              { label: "RetroDECK", data: "retrodeck" },
              { label: "EmuDeck", data: "emudeck" },
            ]}
            onChange={(option) => setInstallation(option.data)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const result = await saveEmulatorInstallation(installation);
                setMessage(result.message || "Installation saved");
              })
            }
          >
            Save installation choice (restart required)
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      <EmudeckLibrary revision={libraryRevision} />
      <PanelSection title="EmuParadise catalogue">
        <PanelSectionRow>
          <TextField
            label="Search games"
            value={query}
            disabled={busy}
            onChange={(event) => {
              setQuery(event.target.value);
              setResults([]);
              setSelected(null);
              setDownloads([]);
              setRomId(null);
              setMessage("");
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy || query.trim().length < 2 || query.trim().length > 100}
            onClick={search}
          >
            Search EmuParadise
          </ButtonItem>
        </PanelSectionRow>
        {results.map((item) => (
          <PanelSectionRow key={item.page_url}>
            <ButtonItem layout="below" disabled={busy} onClick={() => choose(item)}>
              {item.title} – {platformLabel(item.platform)}
            </ButtonItem>
          </PanelSectionRow>
        ))}
        {selected &&
          downloads.map((option) => (
            <PanelSectionRow key={`${option.provider}:${option.page_url}`}>
              <ButtonItem layout="below" disabled={busy} description={option.filename} onClick={() => download(option)}>
                {option.archive.toUpperCase()} – {option.size || "Size unknown"} –{" "}
                {option.provider === "romspedia" ? "Romspedia" : "RomsDL"}
              </ButtonItem>
            </PanelSectionRow>
          ))}
        {romId !== null && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy}
              description="Keeps saves and any Steam shortcut."
              onClick={() =>
                run(async () => {
                  const result = await removeRom(romId);
                  setMessage(result.success ? "Installed ROM deleted." : result.message || "Deletion failed");
                  setLibraryRevision((value) => value + 1);
                })
              }
            >
              Delete installed ROM
            </ButtonItem>
          </PanelSectionRow>
        )}
        {message && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => undefined}>
              {message}
            </ButtonItem>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
};
