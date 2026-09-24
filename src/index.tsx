import { definePlugin, addEventListener, removeEventListener, toaster } from "@decky/api";
import { useState } from "react";
import { ButtonItem, PanelSection, PanelSectionRow, Focusable } from "@decky/ui";
import { FaGamepad } from "react-icons/fa";
import { CataloguePage } from "./components/CataloguePage";
import { DownloadQueue } from "./components/DownloadQueue";
import { EdenPage } from "./components/EdenPage";
import { downloadLatestRelease, getEdenStatus, logError } from "./api/backend";
import { showToast } from "./utils/toast";
import { updateDownload, getDownloadState, removeDownload } from "./utils/downloadStore";
import { handleGlobalDownloadFailure } from "./utils/downloadFailure";
import { setLaunchOptionsConfirmed } from "./utils/steamShortcuts";
import { detach } from "./utils/detach";
import { collapseQamOnDismount } from "./utils/qamExpansion";
import type { DownloadProgressEvent, DownloadCompleteEvent, DownloadFailedEvent } from "./types";

let currentPage = "main";
let lastEdenLobbyState: { game: string; count: number } | null = null;
function Tender() {
  const [page, setPage] = useState(currentPage);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const navigate = (next: string) => {
    currentPage = next;
    setPage(next);
  };
  if (page === "search")
    return (
      <Focusable onCancelButton={() => navigate("main")}>
        <CataloguePage onBack={() => navigate("main")} />
      </Focusable>
    );
  if (page === "downloads")
    return (
      <Focusable onCancelButton={() => navigate("main")}>
        <DownloadQueue onBack={() => navigate("main")} />
      </Focusable>
    );
  if (page === "eden")
    return (
      <Focusable onCancelButton={() => navigate("main")}>
        <EdenPage onBack={() => navigate("main")} />
      </Focusable>
    );
  return (
    <PanelSection>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => navigate("search")}>
          Search
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => navigate("downloads")}>
          Downloads
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => navigate("eden")}>
          Eden
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          disabled={busy}
          description="Saves Tender.zip to Downloads for manual developer installation."
          onClick={() => {
            setBusy(true);
            setError(false);
            setMessage("Checking the latest GitHub release…");
            void downloadLatestRelease()
              .then((result) => {
                if (!result.success) throw new Error(result.message || "Download failed");
                setMessage(result.message || "Downloaded Tender.zip");
              })
              .catch((cause) => {
                console.error(cause);
                setError(true);
                setMessage(String(cause));
              })
              .finally(() => setBusy(false));
          }}
        >
          {busy ? "Downloading update…" : "Download latest Tender"}
        </ButtonItem>
      </PanelSectionRow>
      {message && (
        <PanelSectionRow>
          <div
            role={error ? "alert" : "status"}
            style={{ color: error ? "#ff7070" : undefined, overflowWrap: "anywhere" }}
          >
            {message}
          </div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
}
export default definePlugin(() => {
  const checkEdenLobbies = async () => {
    try {
      const status = await getEdenStatus();
      if (!status.running || !status.game_name) {
        lastEdenLobbyState = null;
        return;
      }

      const previous = lastEdenLobbyState;
      if (
        status.lobby_count > 0 &&
        (previous === null || previous.game !== status.game_name || status.lobby_count > previous.count)
      ) {
        showToast(
          `${status.lobby_count} Eden public room${status.lobby_count === 1 ? "" : "s"} open for ${status.game_name}`,
        );
      }
      lastEdenLobbyState = { game: status.game_name, count: status.lobby_count };
    } catch (cause) {
      // Lobby availability is an optional convenience; don't surface transient
      // network/process-probe failures as user-facing errors.
      console.debug("Tender: Eden lobby check failed", cause);
    }
  };

  void checkEdenLobbies();
  const edenLobbyTimer = window.setInterval(() => void checkEdenLobbies(), 60_000);

  const downloadProgressListener = addEventListener<[DownloadProgressEvent]>(
    "download_progress",
    (data: DownloadProgressEvent) => {
      // A cancel is an explicit discard — drop the entry entirely so no
      // "Cancelled" row lingers in the queue view or the QAM summary count
      // (#149 downloads-round). Both the running-cancel and the paused-cancel
      // backend paths emit this terminal frame, so this is the single place the
      // store drops a cancelled download. Every other status updates in place.
      if (data.status === "cancelled") {
        removeDownload(data.rom_id);
        return;
      }
      // Carry the server's resumability verdict from the frame; a frame that
      // omits it (older shape) keeps the prior value instead of clobbering it.
      const prev = getDownloadState().find((d) => d.rom_id === data.rom_id);
      updateDownload({
        rom_id: data.rom_id,
        rom_name: data.rom_name,
        platform_name: data.platform_name,
        file_name: data.file_name,
        status: data.status as "queued" | "downloading" | "completed" | "failed" | "cancelled" | "paused",
        progress: data.progress,
        bytes_downloaded: data.bytes_downloaded,
        total_bytes: data.total_bytes,
        resumable: data.resumable ?? prev?.resumable ?? false,
      });
    },
  );

  const downloadCompleteListener = addEventListener<[DownloadCompleteEvent]>(
    "download_complete",
    (data: DownloadCompleteEvent) => {
      const prev = getDownloadState().find((d) => d.rom_id === data.rom_id);
      updateDownload({
        rom_id: data.rom_id,
        rom_name: data.rom_name,
        platform_name: data.platform_name,
        file_name: prev?.file_name ?? "",
        status: "completed",
        progress: 1,
        bytes_downloaded: prev?.bytes_downloaded ?? 0,
        total_bytes: prev?.total_bytes ?? 0,
        resumable: data.resumable ?? prev?.resumable ?? false,
      });
      showToast(`Downloaded ${data.rom_name}`);

      // The ROM is now installed — its shortcut's launch options must carry the
      // full launch command (was "" while uninstalled). The backend resolved
      // the bound appId for this rom_id and put it on the payload, so confirm-set
      // the new launch options directly. ``app_id`` is null when the ROM isn't
      // synced yet (no shortcut) — no-op; the next sync writes the command at
      // creation time.
      if (data.app_id !== null) {
        const appId = data.app_id;
        detach(
          (async () => {
            try {
              const ok = await setLaunchOptionsConfirmed(appId, data.launch_options);
              if (!ok) {
                logError(`download_complete: failed to confirm launch options for rom ${data.rom_id} (appId ${appId})`);
              }
            } catch (e) {
              logError(`download_complete: failed to set launch options for rom ${data.rom_id}: ${e}`);
            }
          })(),
        );
      }
    },
  );

  const downloadFailedListener = addEventListener<[DownloadFailedEvent]>(
    "download_failed",
    (data: DownloadFailedEvent) => handleGlobalDownloadFailure(data, { getDownloadState, updateDownload }, toaster),
  );

  return {
    name: "Tender",
    titleView: <div>Tender</div>,
    content: <Tender />,
    icon: <FaGamepad />,
    onDismount() {
      removeEventListener("download_progress", downloadProgressListener);
      removeEventListener("download_complete", downloadCompleteListener);
      removeEventListener("download_failed", downloadFailedListener);
      window.clearInterval(edenLobbyTimer);
      collapseQamOnDismount();
    },
  };
});
