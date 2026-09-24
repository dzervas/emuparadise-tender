import { callable } from "@decky/api";
import { detach } from "../utils/detach";
import type {
  DownloadItem,
  InstalledRom,
  RommErrorCode,
  TargetOccupiedResult,
  CandidatesFoundResult,
  UnusableNamesakeResult,
  CandidateVanishedResult,
  RenameCollisionsResult,
  CollisionChoice,
} from "../types";

export interface BackendResult {
  success: boolean;
  message: string;
  reason?: RommErrorCode;
}

export const startDownload = callable<
  [number, boolean, string | null, CollisionChoice | null, boolean],
  | BackendResult
  | TargetOccupiedResult
  | CandidatesFoundResult
  | UnusableNamesakeResult
  | CandidateVanishedResult
  | RenameCollisionsResult
>("start_download");

export const cancelDownload = callable<[number], BackendResult>("cancel_download");

export const pauseDownload = callable<[number], BackendResult>("pause_download");

export const resumeDownload = callable<[number], BackendResult | TargetOccupiedResult>("resume_download");

export const getDownloadQueue = callable<[], { downloads: DownloadItem[] }>("get_download_queue");

export const clearCompletedDownloads = callable<[], { success: boolean; cleared: number }>("clear_completed_downloads");

export const getInstalledRom = callable<[number], InstalledRom | null>("get_installed_rom");

export const removeRom = callable<[number], BackendResult>("remove_rom");

export const fetchCoverBase64 = callable<[number], { base64: string | null }>("fetch_cover_base64");

export const logInfo = (msg: string) => {
  detach(callable<[string], void>("log_info")(msg));
};

export const logError = (msg: string) => {
  detach(callable<[string], void>("log_error")(msg));
};

export interface CatalogueInspection {
  success: boolean;
  message?: string;
  entry?: { title: string; platform: string; description: string };
  download?: { filename: string; provider: string };
  system?: string;
}

export interface CatalogueImport {
  shortcut_owner?: "tender" | "srm";
  success: boolean;
  message?: string;
  rom_id?: number;
  app_id?: number | null;
  shortcut?: import("../types").SyncAddItem;
}

export const inspectCatalogueEntry = callable<[string, string, string], CatalogueInspection>("inspect_catalogue_entry");

export const importCatalogueEntry = callable<[string, string, string], CatalogueImport>("import_catalogue_entry");

export const bindCatalogueShortcut = callable<[number, number], BackendResult>("bind_catalogue_shortcut");

export const getEmulatorInstallation = callable<
  [],
  { selection: string; active_selection?: string; restart_required?: boolean; message?: string }
>("get_emulator_installation");

export const saveEmulatorInstallation = callable<[string], BackendResult & { restart_required?: boolean }>(
  "save_emulator_installation",
);

export interface SrmStatus {
  enabled: boolean;
  ready: boolean;
  busy: boolean;
  message?: string;
  job?: { status: string; message: string };
}

export interface CatalogueItem {
  rom_id: number;
  name: string;
  installed: boolean;
}

export const getSrmStatus = callable<[], SrmStatus>("get_srm_status");

export const updateSrmLibrary = callable<[], BackendResult>("update_srm_library");

export const listCatalogueEntries = callable<[], { success: boolean; items: CatalogueItem[] }>(
  "list_catalogue_entries",
);

export interface CatalogueSearchItem {
  cover_url?: string | null;
  title: string;
  platform: string;
  page_url: string;
}

export interface CatalogueDownloadOption {
  provider: string;
  page_url: string;
  filename: string;
  archive: string;
  size: string | null;
  region?: string | null;
}

export const searchCatalogue = callable<
  [string, string?],
  {
    success: boolean;
    items: CatalogueSearchItem[];
    message?: string;
  }
>("search_catalogue");

export const getCatalogueDownloads = callable<
  [string],
  {
    success: boolean;
    items: CatalogueDownloadOption[];
    messages?: string[];
    provider_results?: { provider: string; success: boolean; count: number; message: string }[];
    message?: string;
  }
>("get_catalogue_downloads");

export const getCatalogueArtwork = callable<[string], { cover_url?: string | null }>("get_catalogue_artwork");

export const downloadLatestRelease = callable<[], { success: boolean; message?: string }>("download_latest_release");


export interface EdenLobby {
  name: string;
  players: number;
  max_players: number | null;
  has_password: boolean;
}

export interface EdenStatus {
  running: boolean;
  pid?: number;
  game_name: string | null;
  rom_path: string | null;
  title_id: string | null;
  lobby_count: number;
  lobbies: EdenLobby[];
  total_lobbies: number;
  lobby_error?: string | null;
}

export const getEdenStatus = callable<[], EdenStatus>("get_eden_status");


export const sendEdenHotkey = callable<
  [string],
  { success: boolean; message: string }
>("send_eden_hotkey");
