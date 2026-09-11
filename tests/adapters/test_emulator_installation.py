import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from adapters.emulator_installation import EmulatorInstallationAdapter, InstallationCatalogueAdapter
from domain.emulator_commands import classify_command, option_to_invocation
from domain.shortcut_data import build_launch_options, resolve_emulator_invocation


def emudeck(monkeypatch, tmp_path):
    root = tmp_path / "SD card" / "Emulation"
    (root / "roms" / "gb").mkdir(parents=True)
    installation = SimpleNamespace(
        kind="emudeck",
        roms_dir=lambda: str(root / "roms"),
        root=lambda: str(root),
        saves_root=lambda: str(root / "saves"),
        bios_dir=lambda: str(root / "bios"),
        rom_location=lambda system: SimpleNamespace(dir=str(root / "roms" / system)),
    )
    monkeypatch.setattr("adapters.emulator_installation.detect", lambda home: [installation])
    return EmulatorInstallationAdapter(user_home=str(tmp_path), preference="emudeck", retrodeck_paths=Mock()), root


def test_emudeck_uses_selected_configured_root(monkeypatch, tmp_path):
    adapter, root = emudeck(monkeypatch, tmp_path)
    assert adapter.roms_path() == str(root / "roms")
    assert adapter.bios_path() == str(root / "bios")
    adapter.validate_system("gb")
    (root / "roms" / "gb").rmdir()
    (root / "roms" / "gb").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="system's ROM folder"):
        adapter.validate_system("gb")


def test_host_launch_preserves_core_and_quotes_paths(monkeypatch, tmp_path):
    adapter, root = emudeck(monkeypatch, tmp_path)
    launcher = root / "tools" / "retroarch.sh"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\nexit 1\n")
    launcher.chmod(0o755)
    cores = root / "cores"
    cores.mkdir()
    (cores / "gambatte_libretro.so").touch()
    rules = tmp_path / "ES-DE" / "custom_systems" / "es_find_rules.xml"
    rules.parent.mkdir(parents=True)
    rules.write_text(
        f'<ruleList><emulator name="RETROARCH"><rule type="staticpath"><entry>{launcher}</entry></rule></emulator>'
        f'<core name="RETROARCH"><rule type="corepath"><entry>{cores}</entry></rule></core></ruleList>'
    )
    command = "%EMULATOR_RETROARCH% -L %CORE_RETROARCH%/gambatte_libretro.so %ROM%"
    catalogue = Mock()
    catalogue.get_emulator_options.return_value = {
        "available": True,
        "options": [classify_command("Gambatte", command)],
    }
    wrapper = InstallationCatalogueAdapter(catalogue=catalogue, installation=adapter)
    option = wrapper.get_emulator_options("gb")["options"][0]
    invocation = option_to_invocation(option)
    assert invocation is not None
    assert invocation.core_so == "gambatte_libretro"
    rom = str(root / "roms" / "gb" / "A game.gb")
    launch = build_launch_options(resolve_emulator_invocation({}, invocation), rom)
    assert shlex.split(launch) == [str(launcher), "-L", str(cores / "gambatte_libretro.so"), rom]
    assert "net.retrodeck.retrodeck" not in launch


def test_missing_emudeck_launcher_never_falls_back_to_retrodeck(monkeypatch, tmp_path):
    adapter, _ = emudeck(monkeypatch, tmp_path)
    catalogue = Mock()
    catalogue.get_emulator_options.return_value = {
        "available": True,
        "options": [
            classify_command("Gambatte", "%EMULATOR_RETROARCH% -L %CORE_RETROARCH%/gambatte_libretro.so %ROM%")
        ],
    }
    wrapper = InstallationCatalogueAdapter(catalogue=catalogue, installation=adapter)
    with pytest.raises(ValueError, match="configured launcher"):
        resolve_emulator_invocation({}, wrapper.get_default_emulator("gb"))


def test_retrodeck_keeps_original_paths_and_commands(monkeypatch, tmp_path):
    monkeypatch.setattr("adapters.emulator_installation.detect", lambda home: [SimpleNamespace(kind="retrodeck")])
    original = Mock()
    original.roms_path.return_value = "/configured/retrodeck/roms"
    adapter = EmulatorInstallationAdapter(user_home=str(tmp_path), preference="retrodeck", retrodeck_paths=original)
    assert adapter.roms_path() == "/configured/retrodeck/roms"
    catalogue = Mock()
    wrapper = InstallationCatalogueAdapter(catalogue=catalogue, installation=adapter)
    assert wrapper.get_default_emulator("gb") is catalogue.get_default_emulator.return_value


def test_adapter_imports_without_deckys_missing_etree():
    """A fresh process must not rely on pytest's already imported stdlib modules."""
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
sys.modules["xml.etree"] = None
from adapters.emulator_installation import EmulatorInstallationAdapter
""",
        ],
        env={**os.environ, "PYTHONPATH": "py_modules"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
