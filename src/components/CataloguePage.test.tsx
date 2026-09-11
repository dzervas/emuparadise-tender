import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CataloguePage } from "./CataloguePage";
import {
  bindCatalogueShortcut,
  importCatalogueEntry,
  searchCatalogue,
  getCatalogueDownloads,
  startDownload,
} from "../api/backend";
import { addShortcut } from "../utils/steamShortcuts";

vi.mock("@decky/ui", () => ({
  PanelSection: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PanelSectionRow: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ButtonItem: ({
    children,
    onClick,
    disabled,
  }: {
    children: React.ReactNode;
    onClick: () => void;
    disabled?: boolean;
  }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
  TextField: ({ label, ...props }: { label: string }) => <input aria-label={label} {...props} />,
  DropdownItem: () => <div />,
}));
vi.mock("../api/backend", () => ({
  searchCatalogue: vi.fn(),
  getCatalogueDownloads: vi.fn(),
  importCatalogueEntry: vi.fn(),
  bindCatalogueShortcut: vi.fn(),
  getEmulatorInstallation: vi.fn(async () => ({ selection: "auto" })),
  saveEmulatorInstallation: vi.fn(),
  fetchCoverBase64: vi.fn(async () => ({ base64: null })),
  startDownload: vi.fn(),
  removeRom: vi.fn(),
}));
vi.mock("./EmudeckLibrary", () => ({ EmudeckLibrary: () => null }));
vi.mock("../utils/steamShortcuts", () => ({ addShortcut: vi.fn() }));
vi.mock("../patches/gameDetailPatch", () => ({ registerRomMAppId: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("SteamClient", { Apps: { RemoveShortcut: vi.fn(), SetCustomArtworkForApp: vi.fn() } });
  vi.mocked(searchCatalogue).mockResolvedValue({
    success: true,
    items: [{ title: "Homebrew", platform: "Nintendo_Game_Boy_ROMs", page_url: "https://catalogue/game" }],
  });
  vi.mocked(getCatalogueDownloads).mockResolvedValue({
    success: true,
    items: [
      {
        filename: "Homebrew.zip",
        archive: "zip",
        size: "20 KB",
        provider: "romspedia",
        page_url: "https://provider/game",
      },
    ],
  });
  vi.mocked(importCatalogueEntry).mockResolvedValue({
    success: true,
    rom_id: 4503599627370496,
    app_id: null,
    shortcut: {
      rom_id: 4503599627370496,
      name: "Homebrew",
      exe: "/plugin/bin/rom-launcher",
      start_dir: "/plugin/bin",
      launch_options: "",
      platform_name: "GB",
    },
  });
  vi.mocked(addShortcut).mockResolvedValue(123);
  vi.mocked(bindCatalogueShortcut).mockResolvedValue({ success: true, message: "" });
  vi.mocked(startDownload).mockResolvedValue({ success: true, message: "" });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function select() {
  render(<CataloguePage onBack={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Homebrew" } });
  fireEvent.click(screen.getByText("Search EmuParadise"));
  fireEvent.click(await screen.findByText("Homebrew – Nintendo Game Boy"));
  return screen.findByText("ZIP – 20 KB – Romspedia");
}

it("searches, shows download metadata, and downloads the selected source", async () => {
  fireEvent.click(await select());
  await screen.findByText("Download queued. Progress is on Downloads.");
  expect(searchCatalogue).toHaveBeenCalledWith("Homebrew");
  expect(importCatalogueEntry).toHaveBeenCalledWith("https://catalogue/game", "romspedia", "https://provider/game");
  expect(startDownload).toHaveBeenCalledWith(4503599627370496, false, null, null, false);
});
it("rolls back a new shortcut and does not download if binding fails", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.mocked(bindCatalogueShortcut).mockResolvedValue({ success: false, message: "Binding refused" });
  fireEvent.click(await select());
  await screen.findByText("Error: Binding refused");
  expect(SteamClient.Apps.RemoveShortcut).toHaveBeenCalledWith(123);
  expect(startDownload).not.toHaveBeenCalled();
});
it("keeps EmuDeck shortcut ownership with SRM", async () => {
  vi.mocked(importCatalogueEntry).mockResolvedValue({ success: true, rom_id: 4503599627370496, shortcut_owner: "srm" });
  fireEvent.click(await select());
  await screen.findByText("Download queued. Progress is on Downloads. Update Steam library after it finishes.");
  expect(addShortcut).not.toHaveBeenCalled();
  expect(startDownload).toHaveBeenCalledOnce();
});
it("clears old sources after the query changes", async () => {
  await select();
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Other" } });
  expect(screen.queryByText("ZIP – 20 KB – Romspedia")).toBeNull();
  expect(screen.queryByText("Homebrew – Nintendo Game Boy")).toBeNull();
});
it("limits the result list to five games", async () => {
  vi.mocked(searchCatalogue).mockResolvedValue({
    success: true,
    items: Array.from({ length: 7 }, (_, i) => ({
      title: `Game ${i}`,
      platform: "GB_ROMs",
      page_url: `https://catalogue/${i}`,
    })),
  });
  render(<CataloguePage onBack={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Game" } });
  fireEvent.click(screen.getByText("Search EmuParadise"));
  await screen.findByText("Game 0 – GB");
  expect(screen.getAllByText(/Game \d – GB/)).toHaveLength(5);
});
it("surfaces search failure instead of retaining previous choices", async () => {
  const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.mocked(searchCatalogue).mockResolvedValue({ success: false, items: [], message: "Source unavailable" });
  render(<CataloguePage onBack={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Game" } });
  fireEvent.click(screen.getByText("Search EmuParadise"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Source unavailable");
  expect(screen.getByRole("alert")).toHaveStyle({ color: "#ff7070" });
  expect(getCatalogueDownloads).not.toHaveBeenCalled();
  expect(logged).toHaveBeenCalledWith("Tender catalogue request failed", expect.any(Error));
});

it("times out an unanswered search, ignores its late reply, and allows retry", async () => {
  vi.useFakeTimers();
  const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
  let finish!: (value: Awaited<ReturnType<typeof searchCatalogue>>) => void;
  vi.mocked(searchCatalogue).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  render(<CataloguePage onBack={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Game" } });
  fireEvent.click(screen.getByText("Search EmuParadise"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(30000);
  });
  expect(screen.getByRole("alert")).toHaveTextContent("Tender did not respond in time");
  expect(screen.getByRole("alert")).toHaveStyle({ color: "#ff7070" });
  expect(screen.getByText("Search EmuParadise")).not.toBeDisabled();
  expect(screen.queryByText("Searching EmuParadise…")).toBeNull();
  expect(logged).toHaveBeenCalledWith("Tender catalogue request failed", expect.any(Error));
  await act(async () => {
    finish({ success: true, items: [{ title: "Stale", platform: "GB_ROMs", page_url: "stale" }] });
  });
  expect(screen.queryByText("Stale – GB")).toBeNull();
  await act(async () => {
    fireEvent.click(screen.getByText("Search EmuParadise"));
  });
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByText("Homebrew – Nintendo Game Boy")).toBeInTheDocument();
});
