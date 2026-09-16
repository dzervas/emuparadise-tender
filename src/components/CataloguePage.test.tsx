import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { showModal } from "@decky/ui";
import { CataloguePage } from "./CataloguePage";
import {
  searchCatalogue,
  getCatalogueDownloads,
  importCatalogueEntry,
  startDownload,
  saveEmulatorInstallation,
} from "../api/backend";

vi.mock("./qam/WidePage", () => ({ WidePage: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("./EmudeckLibrary", () => ({ EmudeckLibrary: () => null }));
vi.mock("../api/backend", () => ({
  searchCatalogue: vi.fn(),
  getCatalogueDownloads: vi.fn(),
  importCatalogueEntry: vi.fn(),
  startDownload: vi.fn(),
  getEmulatorInstallation: vi.fn(async () => ({ selection: "auto", active_selection: "auto" })),
  saveEmulatorInstallation: vi.fn(async () => ({ success: true, restart_required: true })),
  getCatalogueArtwork: vi.fn(async () => ({ cover_url: "https://r.mprd.se/cover.png" })),
  bindCatalogueShortcut: vi.fn(),
  fetchCoverBase64: vi.fn(async () => ({ base64: null })),
  removeRom: vi.fn(),
}));
vi.mock("@decky/ui", () => {
  const wrap = ({ children }: { children: ReactNode }) => <div>{children}</div>;
  const button = ({
    children,
    onClick,
    disabled,
  }: {
    children: ReactNode;
    onClick: () => void;
    disabled?: boolean;
  }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
  return {
    PanelSection: wrap,
    PanelSectionRow: wrap,
    ModalRoot: wrap,
    ButtonItem: button,
    DialogButton: button,
    showModal: vi.fn(),
    TextField: ({ label, ...props }: { label: string }) => <input aria-label={label} {...props} />,
    DropdownItem: ({
      label,
      selectedOption,
      rgOptions,
      onChange,
    }: {
      label: string;
      selectedOption: string;
      rgOptions: { label: string; data: string }[];
      onChange: (option: { data: string }) => void;
    }) => (
      <select aria-label={label} value={selectedOption} onChange={(e) => onChange({ data: e.target.value })}>
        {rgOptions.map((o) => (
          <option key={o.data} value={o.data}>
            {o.label}
          </option>
        ))}
      </select>
    ),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(searchCatalogue).mockResolvedValue({
    success: true,
    items: Array.from({ length: 8 }, (_, i) => ({
      title: `Game ${i}`,
      platform: "Sony_Playstation_2_ISOs",
      page_url: `https://example.org/${i}`,
      cover_url: "https://r.mprd.se/cover.png",
    })),
  });
  vi.mocked(getCatalogueDownloads).mockResolvedValue({
    success: true,
    items: [
      {
        provider: "vimm",
        page_url: "https://vimm.net/vault/1",
        filename: "Game.zip",
        archive: "zip",
        region: "USA",
        size: "10 MB",
      },
    ],
  });
  vi.mocked(importCatalogueEntry).mockResolvedValue({ success: true, rom_id: 42, shortcut_owner: "srm" });
  vi.mocked(startDownload).mockResolvedValue({ success: true, message: "Queued" });
});

it("Enter sends the selected platform and retains all returned results with artwork", async () => {
  render(<CataloguePage onBack={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Platform"), { target: { value: "ps2" } });
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Game" } });
  fireEvent.keyDown(screen.getByLabelText("Search games"), { key: "Enter" });
  await screen.findByRole("button", { name: /Game 7/ });
  expect(searchCatalogue).toHaveBeenCalledWith("Game", "ps2");
  expect(document.querySelectorAll("img")).toHaveLength(8);
});

it("opens provider choices in a modal and queues the chosen source", async () => {
  render(<CataloguePage onBack={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Search games"), { target: { value: "Game" } });
  fireEvent.click(screen.getByText("Search EmuParadise"));
  fireEvent.click(await screen.findByRole("button", { name: /Game 0/ }));
  expect(showModal).toHaveBeenCalledOnce();
  render(vi.mocked(showModal).mock.calls[0]![0]);
  fireEvent.click(await screen.findByRole("button", { name: /Vimm’s Lair/ }));
  await screen.findByText("Download queued. Open Downloads for progress.");
  expect(importCatalogueEntry).toHaveBeenCalledWith("https://example.org/0", "vimm", "https://vimm.net/vault/1");
  expect(startDownload).toHaveBeenCalledWith(42, false, null, null, false);
});

it("retains installation selection and confirmation outside the search form", async () => {
  render(<CataloguePage onBack={vi.fn()} />);
  expect(screen.queryByLabelText("Installation")).toBeNull();
  fireEvent.click(screen.getByText("Installation & installed games"));
  await screen.findByText(/Loaded installation choice/);
  fireEvent.change(screen.getByLabelText("Installation"), { target: { value: "emudeck" } });
  fireEvent.click(screen.getByText("Save installation choice"));
  await waitFor(() => expect(saveEmulatorInstallation).toHaveBeenCalledWith("emudeck"));
  await screen.findByText(/Saved choice: emudeck/);
});
