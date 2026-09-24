import { useCallback, useEffect, useState } from "react";
import { ButtonItem, Navigation, PanelSection, PanelSectionRow } from "@decky/ui";
import { getEdenStatus, type EdenStatus } from "../api/backend";
import { showToast } from "../utils/toast";

const HID = {
  B: 5,
  C: 6,
  L: 15,
  N: 17,
  R: 21,
  Comma: 54,
  Period: 55,
  LControl: 224,
} as const;

type EdenKey = keyof Pick<typeof HID, "B" | "C" | "L" | "N" | "R" | "Comma" | "Period">;

function sendEdenHotkey(key: EdenKey): void {
  Navigation.CloseSideMenus();

  // Give Gamescope/SteamUI a moment to return keyboard focus to Eden after QAM
  // closes, then inject the exact shortcut Eden already handles itself.
  window.setTimeout(() => {
    try {
      SteamClient.Input.ControllerKeyboardSetKeyState(HID.LControl, true);
      SteamClient.Input.ControllerKeyboardSetKeyState(HID[key], true);
      SteamClient.Input.ControllerKeyboardSetKeyState(HID[key], false);
      SteamClient.Input.ControllerKeyboardSetKeyState(HID.LControl, false);
    } catch (cause) {
      console.error("Tender: failed to send Eden hotkey", cause);
      showToast("Could not send Eden shortcut");
    }
  }, 150);
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
    const timer = window.setInterval(() => void refresh(), 5000);
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
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("B")}>
          Browse library
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("Comma")}>
          Configure Eden
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          disabled={!status?.running || !status?.game_name}
          onClick={() => sendEdenHotkey("Period")}
        >
          Configure current game
        </ButtonItem>
      </PanelSectionRow>

      <PanelSectionRow>
        <div style={{ fontWeight: 600, marginTop: 8 }}>Multiplayer</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("N")}>
          Create room
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("R")}>
          Show current room
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("C")}>
          Direct connect
        </ButtonItem>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!status?.running} onClick={() => sendEdenHotkey("L")}>
          Leave room
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}
