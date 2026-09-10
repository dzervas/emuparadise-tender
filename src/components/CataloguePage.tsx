import { FC, useState, useEffect } from "react";
import { ButtonItem, DropdownItem, PanelSection, PanelSectionRow, TextField } from "@decky/ui";
import {
  getEmulatorInstallation,
  saveEmulatorInstallation,
  bindCatalogueShortcut,
  fetchCoverBase64,
  importCatalogueEntry,
  inspectCatalogueEntry,
  removeRom,
  startDownload,
} from "../api/backend";
import type { CatalogueInspection } from "../api/backend";
import { addShortcut } from "../utils/steamShortcuts";
import { registerRomMAppId } from "../patches/gameDetailPatch";

export const CataloguePage: FC<{ onBack: () => void }> = ({ onBack }) => {
  const [installation, setInstallation] = useState("auto");
  const [catalogueUrl, setCatalogueUrl] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [provider, setProvider] = useState("romspedia");
  const [inspection, setInspection] = useState<CatalogueInspection | null>(null);
  const [romId, setRomId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    void getEmulatorInstallation()
      .then((result) => setInstallation(result.selection))
      .catch((error) => setMessage(String(error)));
  }, []);
  const changed = () => {
    setInspection(null);
    setRomId(null);
    setMessage("");
  };
  const run = (action: () => Promise<void>) => {
    void (async () => {
      setBusy(true);
      try {
        await action();
      } catch (error) {
        setMessage(String(error));
      } finally {
        setBusy(false);
      }
    })();
  };
  const inspect = () =>
    run(async () => {
      const result = await inspectCatalogueEntry(catalogueUrl, provider, downloadUrl);
      setInspection(result.success ? result : null);
      setMessage(
        result.success
          ? "Check the title, platform and file version before importing."
          : result.message || "Source unavailable",
      );
    });
  const importGame = () =>
    run(async () => {
      const result = await importCatalogueEntry(catalogueUrl, provider, downloadUrl);
      if (!result.success || !result.rom_id || !result.shortcut) throw new Error(result.message || "Import failed");
      let appId = result.app_id;
      if (!appId) {
        appId = await addShortcut(result.shortcut);
        if (!appId) throw new Error("Steam could not create the shortcut");
        const bound = await bindCatalogueShortcut(result.rom_id, appId);
        if (!bound.success) {
          SteamClient.Apps.RemoveShortcut(appId);
          throw new Error(bound.message || "Steam shortcut could not be recorded");
        }
      }
      registerRomMAppId(appId);
      setRomId(result.rom_id);
      setMessage("Imported. Download here, or open the game's Steam page.");
      const { base64 } = await fetchCoverBase64(result.rom_id);
      if (base64) await SteamClient.Apps.SetCustomArtworkForApp(appId, base64, "png", 0);
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
            onChange={(option) => {
              setInstallation(option.data);
            }}
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
      <PanelSection title="EmuParadise catalogue">
        <PanelSectionRow>
          <TextField
            label="Catalogue game URL"
            value={catalogueUrl}
            disabled={busy}
            onChange={(e) => {
              changed();
              setCatalogueUrl(e.target.value);
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DropdownItem
            label="Download provider"
            selectedOption={provider}
            disabled={busy}
            rgOptions={[
              { label: "Romspedia", data: "romspedia" },
              { label: "RomsDL", data: "romsdl" },
            ]}
            onChange={(option) => {
              changed();
              setProvider(option.data);
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Download provider's game URL"
            value={downloadUrl}
            disabled={busy}
            onChange={(e) => {
              changed();
              setDownloadUrl(e.target.value);
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !catalogueUrl || !downloadUrl} onClick={inspect}>
            Inspect catalogue and download
          </ButtonItem>
        </PanelSectionRow>
        {inspection?.success && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={busy || romId !== null}
              description={`${inspection.entry?.platform} · ${inspection.download?.filename}`}
              onClick={importGame}
            >
              Import {inspection.entry?.title}
            </ButtonItem>
          </PanelSectionRow>
        )}
        {romId !== null && (
          <>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const result = await startDownload(romId, false, null, null, false);
                    setMessage(
                      result.success
                        ? "Download queued. Progress is on the Downloads page."
                        : result.message || "Download refused",
                    );
                  })
                }
              >
                Download ROM
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={busy}
                description="Keeps saves and the Steam shortcut."
                onClick={() =>
                  run(async () => {
                    const result = await removeRom(romId);
                    setMessage(result.success ? "Installed ROM deleted." : result.message || "Deletion failed");
                  })
                }
              >
                Delete installed ROM
              </ButtonItem>
            </PanelSectionRow>
          </>
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
