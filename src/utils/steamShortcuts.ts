import type { SyncAddItem } from "../types";
import { logError, logInfo } from "../api/backend";
import { delay } from "./pacedOps";
export function getAppDetails(appId: number, timeoutMs = 2000): Promise<SteamAppDetails | null> {
  return new Promise((resolve) => {
    let resolved = false;
    // Declared with `let` BEFORE RegisterForAppDetails so a (hypothetical)
    // synchronous callback fire can't hit the temporal dead zone when finish()
    // reads reg.
    // eslint-disable-next-line prefer-const -- the `let`-before-register ordering is the TDZ guard; `prefer-const` only sees the single assignment and can't model the closure reading `reg` before the assignment line executes.
    let reg: { unregister: () => void } | undefined;
    const finish = (value: SteamAppDetails | null) => {
      if (resolved) return;
      resolved = true;
      reg?.unregister();
      resolve(value);
    };
    reg = SteamClient.Apps.RegisterForAppDetails(appId, (details) => {
      if (details) finish(details);
    });
    setTimeout(() => finish(null), timeoutMs);
  });
}

export function setLaunchOptionsConfirmed(appId: number, value: string, timeoutMs = 2000): Promise<boolean> {
  return new Promise((resolve) => {
    let resolved = false;
    // Declared with `let` BEFORE RegisterForAppDetails so a (hypothetical)
    // synchronous callback fire can't hit the temporal dead zone when finish()
    // reads reg.
    // eslint-disable-next-line prefer-const -- the `let`-before-register ordering is the TDZ guard; `prefer-const` only sees the single assignment and can't model the closure reading `reg` before the assignment line executes.
    let reg: { unregister: () => void } | undefined;
    const finish = (matched: boolean) => {
      if (resolved) return;
      resolved = true;
      reg?.unregister();
      resolve(matched);
    };

    SteamClient.Apps.SetAppLaunchOptions(appId, value);

    reg = SteamClient.Apps.RegisterForAppDetails(appId, (details) => {
      if (!details) return;
      const current = details.strLaunchOptions ?? details.LaunchOptions ?? "";
      if (current === value) finish(true);
    });

    setTimeout(() => finish(false), timeoutMs);
  });
}

async function waitForAppOverview(appId: number, timeoutMs: number): Promise<boolean> {
  const POLL_INTERVAL_MS = 100;
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (appStore.GetAppOverviewByAppID(appId)) return true;
    if (Date.now() >= deadline) return false;
    await delay(POLL_INTERVAL_MS);
  }
}

export async function addShortcut(data: SyncAddItem): Promise<number | null> {
  try {
    // AddShortcut ignores most params (confirmed by MoonDeck plugin) —
    // must use Set* calls after creation to apply name, exe, startDir, launchOptions.
    const appId = await SteamClient.Apps.AddShortcut(data.name, data.exe, "", "");

    if (!appId) return null;

    // Wait for Steam to register the new app's overview before setting
    // properties. Poll for readiness instead of a blind 500ms; on timeout,
    // proceed anyway (same net behaviour as the old fixed wait).
    if (!(await waitForAppOverview(appId, 1000))) {
      logInfo(`addShortcut: overview for ${appId} not ready within 1000ms; proceeding anyway`);
    }

    SteamClient.Apps.SetShortcutName(appId, data.name);
    SteamClient.Apps.SetShortcutExe(appId, data.exe);
    SteamClient.Apps.SetShortcutStartDir(appId, data.start_dir);
    // A freshly created shortcut's launch options are already empty. For an
    // uninstalled ROM (launch_options ""), there is nothing to write or confirm,
    // so skip both SetAppLaunchOptions and the confirm poll — the confirm poll's
    // RegisterForAppDetails forces Steam to load+cache a fat AppDetails object
    // per call, so skipping it for the majority uninstalled case avoids that
    // heap hit. A non-empty command (installed ROM) still takes the confirmed
    // write (#827).
    if (data.launch_options !== "") {
      await setLaunchOptionsConfirmed(appId, data.launch_options);
    }

    return appId;
  } catch (e) {
    logError(`Failed to add shortcut for ${data.name}: ${e}`);
    return null;
  }
}
