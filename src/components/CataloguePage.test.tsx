import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CataloguePage } from "./CataloguePage";
import { bindCatalogueShortcut, importCatalogueEntry, inspectCatalogueEntry } from "../api/backend";
import { addShortcut } from "../utils/steamShortcuts";

vi.mock("@decky/ui", () => ({
  PanelSection: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
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
  inspectCatalogueEntry: vi.fn(),
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
  vi.mocked(inspectCatalogueEntry).mockResolvedValue({
    success: true,
    entry: { title: "Homebrew", platform: "GB", description: "" },
    download: { filename: "Homebrew.zip", provider: "romspedia" },
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
});
afterEach(() => vi.unstubAllGlobals());

async function inspect() {
  render(<CataloguePage onBack={() => undefined} />);
  fireEvent.change(screen.getByLabelText("Catalogue game URL"), { target: { value: "https://catalogue/game" } });
  fireEvent.change(screen.getByLabelText("Download provider's game URL"), {
    target: { value: "https://provider/game" },
  });
  fireEvent.click(screen.getByText("Inspect catalogue and download"));
  return screen.findByText("Import Homebrew");
}

describe("catalogue import", () => {
  it("removes a newly created shortcut if its durable binding fails", async () => {
    vi.mocked(bindCatalogueShortcut).mockResolvedValue({ success: false, message: "Binding refused" });
    fireEvent.click(await inspect());
    await screen.findByText("Error: Binding refused");
    expect(SteamClient.Apps.RemoveShortcut).toHaveBeenCalledWith(123);
    expect(screen.queryByText("Download ROM")).toBeNull();
  });
  it("invalidates inspection when the user changes the source", async () => {
    await inspect();
    await waitFor(() => expect(screen.getByLabelText("Catalogue game URL")).not.toBeDisabled());
    fireEvent.change(screen.getByLabelText("Download provider's game URL"), {
      target: { value: "https://provider/different" },
    });
    expect(screen.queryByText("Import Homebrew")).toBeNull();
    expect(importCatalogueEntry).not.toHaveBeenCalled();
  });
});

it("leaves EmuDeck shortcuts and artwork to SRM", async () => {
  const result = await vi.mocked(importCatalogueEntry).getMockImplementation()!("", "", "");
  vi.mocked(importCatalogueEntry).mockResolvedValue({ ...result, shortcut_owner: "srm" });
  fireEvent.click(await inspect());
  await screen.findByText("Imported. Download the ROM, then update your Steam library below.");
  expect(addShortcut).not.toHaveBeenCalled();
  expect(bindCatalogueShortcut).not.toHaveBeenCalled();
  expect(SteamClient.Apps.SetCustomArtworkForApp).not.toHaveBeenCalled();
});
