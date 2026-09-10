import { FC, useCallback, useEffect, useState } from "react";
import { ButtonItem, PanelSection, PanelSectionRow, TextField } from "@decky/ui";
import {
  getSrmStatus,
  listCatalogueEntries,
  updateSrmLibrary,
  startDownload,
  removeRom,
  importRommCatalogueEntry,
} from "../api/backend";
import type { CatalogueItem, SrmStatus } from "../api/backend";
import { readRunningApps } from "../utils/runningApps";

export const EmudeckLibrary: FC<{ revision: number }> = ({ revision }) => {
  const [status, setStatus] = useState<SrmStatus | null>(null);
  const [items, setItems] = useState<CatalogueItem[]>([]);
  const [selected, setSelected] = useState<CatalogueItem | null>(null);
  const [rommId, setRommId] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState("");
  const refresh = useCallback(async () => {
    const next = await getSrmStatus();
    setStatus(next);
    if (next.enabled) setItems((await listCatalogueEntries()).items);
  }, []);
  useEffect(() => {
    void refresh().catch((error) => setMessage(String(error)));
  }, [refresh, revision]);
  const run = (action: () => Promise<void>) => {
    setBusy(true);
    void action()
      .then(refresh)
      .catch((error) => setMessage(String(error)))
      .finally(() => setBusy(false));
  };
  if (!status?.enabled) return null;
  const disabled = busy || status.busy;
  return (
    <PanelSection title="EmuDeck library">
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={disabled} onClick={() => run(refresh)}>
          Refresh library and SRM status
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <TextField
          label="RomM ROM ID (optional)"
          value={rommId}
          disabled={disabled}
          onChange={(event) => setRommId(event.target.value)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          disabled={disabled || !/^\d+$/.test(rommId)}
          onClick={() =>
            run(async () => {
              const result = await importRommCatalogueEntry(Number(rommId));
              setMessage(
                result.success ? "RomM game imported. Select it below to download." : result.message || "Import failed",
              );
            })
          }
        >
          Import RomM game
        </ButtonItem>
      </PanelSectionRow>
      {items.map((item) => (
        <PanelSectionRow key={item.rom_id}>
          <ButtonItem
            layout="below"
            disabled={disabled}
            description={item.installed ? "Installed" : "Not installed"}
            onClick={() => setSelected(item)}
          >
            {item.name}
          </ButtonItem>
        </PanelSectionRow>
      ))}
      {selected && (
        <>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={disabled}
              onClick={() =>
                run(async () => {
                  const result = await startDownload(selected.rom_id, false, null, null, false);
                  setMessage(
                    result.success
                      ? "Download queued. Wait for completion, then update Steam library."
                      : result.message || "Download failed",
                  );
                })
              }
            >
              Download {selected.name}
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={disabled}
              description="Deletes Tender's recorded ROM files, keeps saves. Update SRM afterward; a stale Steam shortcut may need removal in SRM."
              onClick={() =>
                run(async () => {
                  const result = await removeRom(selected.rom_id);
                  setMessage(
                    result.success
                      ? "ROM deleted. Update Steam library to reconcile SRM shortcuts."
                      : result.message || "Deletion failed",
                  );
                })
              }
            >
              Delete installed {selected.name}
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          disabled={disabled || !status.ready}
          description="Runs all enabled SRM parsers, including games outside Tender. Game Mode closes temporarily and returns when finished."
          onClick={() => setConfirm(true)}
        >
          Update Steam library and restart
        </ButtonItem>
      </PanelSectionRow>
      {confirm && (
        <>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={disabled}
              onClick={() =>
                run(async () => {
                  setConfirm(false);
                  const running = readRunningApps();
                  if (running.apps.length || running.diagnostics !== "SteamUIStore.RunningApps=empty")
                    throw new Error(
                      "Close running games and wait for Steam to report an idle session before restarting Game Mode",
                    );
                  const result = await updateSrmLibrary();
                  setMessage(result.message || (result.success ? "Restarting Game Mode" : "Update failed"));
                })
              }
            >
              Confirm library update and restart now
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={() => setConfirm(false)}>
              Cancel restart
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
      {(message || status.message || status.job?.message) && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => undefined}>
            {message || status.message || status.job?.message}
          </ButtonItem>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};
