import { useCallback, useEffect, useState } from "react";
import { ButtonItem, Navigation, PanelSection, PanelSectionRow } from "@decky/ui";
import { getEdenStatus, sendEdenHotkey as sendEdenHotkeyBackend, type EdenStatus } from "../api/backend";
import { showToast } from "../utils/toast";

type EdenKey = "b" | "c" | "l" | "n" | "r" | "comma" | "period";

function sendEdenHotkey(key: EdenKey): void {
  Navigation.CloseSideMenus();

  // xdotool has already been verified to reach Eden under Gamescope. Run it
  // after QAM has closed so Eden is the active X11/XWayland target again.
  window.setTimeout(() => {
    void sendEdenHotkeyBackend(key)
      .then((result) => {
        if (!result.success) {
          console.error("Tender: Eden hotkey failed", result.message);
          showToast(result.message || "Could not send Eden shortcut");
        }
      })
      .catch((cause) => {
        console.error("Tender: Eden hotkey failed", cause);
        showToast("Could not send Eden shortcut");
      });
  }, 250);
}

function lobbySummary(status: EdenStatus): string {
  if (status.lobby_error) return "Public lobby lookup unavailable";
  if (!status.game_name) return "Game not detected";
  if (status.lobby_count === 0) return "No public rooms for this game";
  return `${status.lobby_count} public room${status.lobby_count === 1 ? "" : "s"} for this game`;
}

export function EdenPage({ onBack }: { onBack: () => void }) {
  const [status, setStatus] = useState<EdenStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setStatus(await getEdenStatus());
    } catch (cause) {
      console.error("Tender: Eden status failed", cause);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <PanelSection>
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={onBack}>
          Back
        </ButtonItem>
      </PanelSectionRow>

      <PanelSectionRow>
        <div>
          <div style={{ fontWeight: 600 }}>Eden</div>
          <div style={{ opacity: 0.75 }}>
            {loading
              ? "Checking…"
              : status?.running
                ? status.game_name || "Running"
                : "Not running"}
          </div>
          {status?.running && <div style={{ opacity: 0.75 }}>{lobbySummary(status)}</div>}
        </div>
      </PanelSectionRow>

      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("comma")}>
          Configure Eden
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          disabled={!status?.running || !status?.game_name}
          onClick={() => sendEdenHotkey("period")}
        >
          Configure current game
        </ButtonItem>
      </PanelSectionRow>

      <PanelSectionRow>
        <div style={{ fontWeight: 600, marginTop: 8 }}>Multiplayer</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("b")}>
          {status?.lobby_count ? `Browse public lobbies (${status.lobby_count})` : "Browse public lobbies"}
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("n")}>
          Create room
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("r")}>
          Show current room
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("c")}>
          Direct connect
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("l")}>
          Leave room
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}
