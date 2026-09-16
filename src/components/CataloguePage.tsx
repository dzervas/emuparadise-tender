import { SiPlaystation, SiPlaystation2, SiPlaystationportable } from "react-icons/si";
import { FaGamepad } from "react-icons/fa";
import { FC, useState, useEffect } from "react";
import {
  ButtonItem,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  TextField,
  DialogButton,
  ModalRoot,
  showModal,
} from "@decky/ui";
import {
  getCatalogueArtwork,
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
import { WidePage } from "./qam/WidePage";

function providerLabel(provider: string): string {
  return (
    ({ romspedia: "Romspedia", romsdl: "RomsDL", vimm: "Vimm’s Lair" } as Record<string, string>)[provider] || provider
  );
}

function platformLabel(section: string): string {
  const names: Record<string, string> = {
    Sony_Playstation_ISOs: "PS1",
    Sony_Playstation_2_ISOs: "PS2",
    PSP_ISOs: "PSP",
    Nintendo_Gamecube_ISOs: "GC",
    Nintendo_Wii_ISOs: "Wii",
    Nintendo_Game_Boy_ROMs: "GB",
    Nintendo_Game_Boy_Color_ROMs: "GBC",
    Nintendo_Gameboy_Advance_ROMs: "GBA",
  };
  return names[section] || section.replace(/_(?:ROMs|ISOs)$/, "").replace(/_/g, " ");
}

// Decky can leave RPCs pending when the Python backend fails to start.
async function catalogueResponse<T>(
  request: Promise<T>,
  timeoutMs = 30000,
  timeoutMessage = "Tender did not respond in time. Its backend may have failed to start, or the source may be slow. Check Tender logs and the plugin_loader journal, then retry.",
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      request,
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error(timeoutMessage)), timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

export const CataloguePage: FC<{ onBack: () => void }> = ({ onBack }) => {
  const [showSettings, setShowSettings] = useState(false);
  const [installation, setInstallation] = useState("auto");
  const [installationLoaded, setInstallationLoaded] = useState(false);
  const [installationNotice, setInstallationNotice] = useState({
    message: "Loading saved installation…",
    error: false,
  });
  const [platform, setPlatform] = useState("any");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogueSearchItem[]>([]);
  const [romId, setRomId] = useState<number | null>(null);
  const [libraryRevision, setLibraryRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const reportError = (cause: unknown) => {
    console.error("Tender catalogue request failed", cause);
    setMessage("");
    setError(String(cause));
  };
  useEffect(() => {
    let mounted = true;
    void catalogueResponse(getEmulatorInstallation())
      .then((result) => {
        if (!mounted) return;
        if (!result.selection)
          throw new Error(result.message || "Tender could not load the saved installation choice.");
        setInstallation(result.selection);
        setInstallationLoaded(true);
        setInstallationNotice({
          message: result.restart_required
            ? `Saved choice: ${result.selection}. Restart Decky to apply it (loaded: ${result.active_selection}).`
            : `Loaded installation choice: ${result.active_selection || result.selection}.`,
          error: false,
        });
      })
      .catch((cause: unknown) => {
        console.error("Tender installation settings failed to load", cause);
        if (mounted) setInstallationNotice({ message: String(cause), error: true });
      });
    return () => {
      mounted = false;
    };
  }, []);
  const run = (action: () => Promise<void>, onError = reportError) => {
    setBusy(true);
    setError("");
    void action()
      .catch(onError)
      .finally(() => setBusy(false));
  };
  const saveInstallation = () =>
    run(
      async () => {
        setInstallationNotice({ message: "Saving installation choice…", error: false });
        const result = await catalogueResponse(
          saveEmulatorInstallation(installation),
          30000,
          "Save was not confirmed. Reload Tender and check the saved choice before retrying. Check the plugin_loader journal if Tender does not respond.",
        );
        if (!result.success) throw new Error(result.message || "Installation could not be saved");
        setInstallationNotice({
          message: result.restart_required
            ? `Saved choice: ${installation}. Restart Decky to apply it.`
            : `Saved choice: ${installation}. No restart needed.`,
          error: false,
        });
      },
      (cause: unknown) => {
        console.error("Tender installation save failed", cause);
        setInstallationNotice({ message: String(cause), error: true });
      },
    );
  const search = () =>
    run(async () => {
      setResults([]);
      setRomId(null);
      setMessage("Searching EmuParadise…");
      const result = await catalogueResponse(searchCatalogue(query.trim(), platform));
      if (!result.success) throw new Error(result.message || "Search failed");
      setResults(result.items);
      setMessage(
        result.items.length
          ? ""
          : ["ps3", "switch"].includes(platform)
            ? `EmuParadise does not provide a ${platform.toUpperCase()} catalogue.`
            : "No supported games found. Try a more specific title.",
      );
    });
  const downloadFor = async (selected: CatalogueSearchItem, option: CatalogueDownloadOption) => {
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
    if (!queued.success) throw new Error(queued.message || "Download refused");
    setMessage(
      `Download queued. Progress is on Downloads.${result.shortcut_owner === "srm" ? " Update Steam library after it finishes." : ""}`,
    );
  };
  return (
    <WidePage title="Search" onBack={onBack}>
      <PanelSection>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => setShowSettings(!showSettings)}>
            {showSettings ? "Back to search" : "Installation & installed games"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
      {showSettings ? (
        <>
          <PanelSection title="Emulator installation">
            <PanelSectionRow>
              <DropdownItem
                label="Installation"
                selectedOption={installation}
                disabled={busy || !installationLoaded}
                rgOptions={[
                  { label: "Auto (RetroDECK first)", data: "auto" },
                  { label: "RetroDECK", data: "retrodeck" },
                  { label: "EmuDeck", data: "emudeck" },
                ]}
                onChange={(option) => {
                  setInstallation(option.data);
                  setInstallationNotice({
                    message: "Choice changed. Save to apply after restarting Decky.",
                    error: false,
                  });
                }}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" disabled={busy || !installationLoaded} onClick={saveInstallation}>
                Save installation choice
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <div
                role={installationNotice.error ? "alert" : "status"}
                style={{ color: installationNotice.error ? "#ff7070" : undefined, overflowWrap: "anywhere" }}
              >
                {installationNotice.message}
              </div>
            </PanelSectionRow>
          </PanelSection>
          <EmudeckLibrary revision={libraryRevision} />
        </>
      ) : (
        <>
          <PanelSection title="EmuParadise">
            <PanelSectionRow>
              <DropdownItem
                label="Platform"
                selectedOption={platform}
                disabled={busy}
                rgOptions={[
                  { label: "Any", data: "any" },
                  ...["ps3", "ps2", "ps1", "psp", "gc", "gb", "gbc", "gba", "switch", "wii"].map((data) => ({
                    label: data.toUpperCase(),
                    data,
                  })),
                ]}
                onChange={(option) => {
                  setPlatform(option.data);
                  setResults([]);
                }}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="Search games"
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.nativeEvent.isComposing &&
                    !busy &&
                    query.trim().length >= 2 &&
                    query.trim().length <= 100
                  ) {
                    event.preventDefault();
                    search();
                  }
                }}
                value={query}
                disabled={busy}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setResults([]);
                  setRomId(null);
                  setMessage("");
                  setError("");
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
            {error && (
              <PanelSectionRow>
                <div role="alert" style={{ color: "#ff7070", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  {error}
                </div>
              </PanelSectionRow>
            )}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(155px, 1fr))",
                gap: 16,
                padding: 12,
              }}
            >
              {results.map((item) => (
                <DialogButton
                  key={item.page_url}
                  disabled={busy}
                  onClick={() => {
                    showModal(<DownloadPicker item={item} onDownload={(option) => downloadFor(item, option)} />);
                  }}
                  style={{ padding: 0, overflow: "hidden", height: "auto", position: "relative", textAlign: "left" }}
                >
                  <CatalogueArt item={item} />
                  <span
                    style={{
                      position: "absolute",
                      right: 6,
                      top: 6,
                      background: "#14202ee8",
                      borderRadius: 4,
                      padding: "3px 6px",
                      fontSize: 11,
                    }}
                  >
                    {item.platform === "Sony_Playstation_ISOs" && (
                      <SiPlaystation aria-hidden style={{ marginRight: 5 }} />
                    )}
                    {item.platform === "Sony_Playstation_2_ISOs" && (
                      <SiPlaystation2 aria-hidden style={{ marginRight: 5 }} />
                    )}
                    {item.platform === "PSP_ISOs" && <SiPlaystationportable aria-hidden style={{ marginRight: 5 }} />}
                    {platformLabel(item.platform)}
                  </span>
                  <div style={{ padding: 10, whiteSpace: "normal", fontSize: 14 }}>{item.title}</div>
                </DialogButton>
              ))}
            </div>
            {romId !== null && (
              <PanelSectionRow>
                <ButtonItem
                  layout="below"
                  disabled={busy}
                  description="Keeps saves and any Steam shortcut."
                  onClick={() =>
                    run(async () => {
                      const result = await removeRom(romId);
                      if (!result.success) throw new Error(result.message || "Deletion failed");
                      setMessage("Installed ROM deleted.");
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
      )}
    </WidePage>
  );
};

const CatalogueArt: FC<{ item: CatalogueSearchItem }> = ({ item }) => {
  const [cover, setCover] = useState(item.cover_url);
  useEffect(() => {
    let active = true;
    if (!item.cover_url)
      void getCatalogueArtwork(item.page_url)
        .then((result) => {
          if (active) setCover(result.cover_url);
        })
        .catch(console.error);
    return () => {
      active = false;
    };
  }, [item]);
  return (
    <div
      style={{
        height: 180,
        background: "linear-gradient(145deg, #30455b, #121d2b)",
        display: "grid",
        placeItems: "center",
      }}
    >
      {cover ? (
        <img
          src={cover}
          alt=""
          style={{ width: "100%", height: "100%", objectFit: "contain" }}
          onError={() => setCover(null)}
        />
      ) : (
        <FaGamepad style={{ opacity: 0.4, fontSize: 40 }} />
      )}
    </div>
  );
};

const DownloadPicker: FC<{
  item: CatalogueSearchItem;
  onDownload: (option: CatalogueDownloadOption) => Promise<void>;
  closeModal?: () => void;
}> = ({ item, onDownload, closeModal }) => {
  const [options, setOptions] = useState<CatalogueDownloadOption[]>([]);
  const [status, setStatus] = useState("Checking all download providers…");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    let active = true;
    void catalogueResponse(getCatalogueDownloads(item.page_url), 75000)
      .then((result) => {
        if (!active) return;
        if (!result.success) throw new Error(result.message || "Download sources unavailable");
        setOptions(result.items);
        setStatus(result.items.length ? "Choose a region and file format." : "No matching published downloads.");
        setError(
          result.provider_results
            ?.filter((p) => !p.success)
            .map((p) => `${providerLabel(p.provider)}: ${p.message}`)
            .join("\n") || "",
        );
      })
      .catch((cause) => {
        console.error(cause);
        if (active) setError(String(cause));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [item.page_url]);
  return (
    <ModalRoot closeModal={closeModal} onCancel={closeModal}>
      <h2 style={{ marginBottom: 4 }}>{item.title}</h2>
      <div style={{ opacity: 0.65, marginBottom: 20 }}>{platformLabel(item.platform)}</div>
      <div role="status">{status}</div>
      <div style={{ maxHeight: "50vh", overflowY: "auto", display: "grid", gap: 10, marginTop: 16 }}>
        {options.map((option) => (
          <DialogButton
            key={`${option.provider}:${option.page_url}`}
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError("");
              void onDownload(option)
                .then(() => setStatus("Download queued. Open Downloads for progress."))
                .catch((cause) => {
                  console.error(cause);
                  setError(String(cause));
                })
                .finally(() => setBusy(false));
            }}
            style={{ height: "auto", padding: 14, textAlign: "left", whiteSpace: "normal" }}
          >
            <div>
              {providerLabel(option.provider)} · {option.region || "Unknown region"}
            </div>
            <div style={{ fontSize: 13, opacity: 0.75 }}>
              {option.archive.toUpperCase()} · {option.size || "Size unknown"}
            </div>
            <div style={{ fontSize: 12, opacity: 0.6 }}>{option.filename}</div>
          </DialogButton>
        ))}
      </div>
      {error && (
        <div role="alert" style={{ color: "#ff7070", whiteSpace: "pre-wrap", marginTop: 12 }}>
          {error}
        </div>
      )}
      <DialogButton onClick={() => closeModal?.()} style={{ marginTop: 16 }}>
        Close
      </DialogButton>
    </ModalRoot>
  );
};
