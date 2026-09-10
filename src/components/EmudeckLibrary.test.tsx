import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { EmudeckLibrary } from "./EmudeckLibrary";
import { getSrmStatus, updateSrmLibrary, removeRom } from "../api/backend";

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
}));
vi.mock("../api/backend", () => ({
  getSrmStatus: vi.fn(),
  listCatalogueEntries: vi.fn(async () => ({
    success: true,
    items: [{ rom_id: 99, name: "Homebrew", installed: true }],
  })),
  updateSrmLibrary: vi.fn(async () => ({ success: true, message: "Queued" })),
  removeRom: vi.fn(async () => ({ success: true })),
  startDownload: vi.fn(),
  importRommCatalogueEntry: vi.fn(),
}));
vi.mock("../utils/runningApps", () => ({
  readRunningApps: () => ({ apps: [], diagnostics: "SteamUIStore.RunningApps=empty" }),
}));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getSrmStatus).mockResolvedValue({ enabled: true, ready: true, busy: false });
});
it("requires confirmation before starting the detached restart", async () => {
  render(<EmudeckLibrary revision={0} />);
  fireEvent.click(await screen.findByText("Update Steam library and restart"));
  expect(updateSrmLibrary).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Confirm library update and restart now"));
  await screen.findByText("Queued");
  expect(updateSrmLibrary).toHaveBeenCalledOnce();
});
it("reports an unsupported environment without offering a restart", async () => {
  vi.mocked(getSrmStatus).mockResolvedValue({ enabled: true, ready: false, busy: false, message: "Missing Xvfb" });
  render(<EmudeckLibrary revision={0} />);
  await screen.findByText("Missing Xvfb");
  expect(screen.getByText("Update Steam library and restart")).toBeDisabled();
  expect(updateSrmLibrary).not.toHaveBeenCalled();
});
it("can delete a persisted ROM without owning a Steam shortcut", async () => {
  render(<EmudeckLibrary revision={0} />);
  fireEvent.click(await screen.findByText("Homebrew"));
  fireEvent.click(screen.getByText("Delete installed Homebrew"));
  await screen.findByText("ROM deleted. Update Steam library to reconcile SRM shortcuts.");
  expect(removeRom).toHaveBeenCalledWith(99);
});
