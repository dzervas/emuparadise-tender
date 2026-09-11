"""One selected installation for catalogue reads, host launchers and file roots."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import replace
from typing import Any, cast

from _vendor.atlas import EmuDeck, detect
from _vendor.atlas._xml import ParseError, fromstring

from domain.emulator_commands import option_to_invocation, select_default_option
from domain.shortcut_data import EmulatorInvocation
from lib.retrodeck_health import RetroDeckConfigHealth


class EmulatorInstallationAdapter:
    def __init__(self, *, user_home: str, preference: str, retrodeck_paths: Any) -> None:
        self._home = user_home
        self._retrodeck = retrodeck_paths
        installations = [item for item in detect(user_home) if item.kind in ("retrodeck", "emudeck")]
        self.available = ("auto", *(item.kind for item in installations))
        self._installation = next(
            (item for item in installations if preference == "auto" or item.kind == preference), None
        )
        self.kind = self._installation.kind if self._installation else preference

    def choose(self):
        if self._installation is None and self.kind in ("auto", "retrodeck"):
            self._installation = next((item for item in detect(self._home) if item.kind == "retrodeck"), None)
        return self._installation

    def _emudeck(self) -> EmuDeck:
        if self.kind != "emudeck" or self._installation is None:
            raise ValueError("The selected EmuDeck installation is unavailable")
        return cast("EmuDeck", self._installation)

    def roms_path(self) -> str:
        if self.kind in ("emudeck", "retrodeck") and self._installation is None:
            raise ValueError("The selected emulator installation is unavailable")
        if self.kind != "emudeck":
            return self._retrodeck.roms_path()
        root = self._emudeck().roms_dir()
        if not root:
            raise ValueError("EmuDeck ES-DE ROMDirectory could not be resolved; repair its configuration first")
        return os.path.realpath(root)

    def saves_path(self) -> str:
        return (
            os.path.realpath(self._emudeck().saves_root()) if self.kind == "emudeck" else self._retrodeck.saves_path()
        )

    def states_path(self) -> str:
        return self.saves_path() if self.kind == "emudeck" else self._retrodeck.states_path()

    def bios_path(self) -> str:
        return os.path.realpath(self._emudeck().bios_dir()) if self.kind == "emudeck" else self._retrodeck.bios_path()

    def retrodeck_home(self) -> str:
        if self.kind == "emudeck" and self._installation is None:
            return ""
        return os.path.realpath(self._emudeck().root()) if self.kind == "emudeck" else self._retrodeck.retrodeck_home()

    def config_path(self) -> str:
        return (
            os.path.join(self._home, ".config", "EmuDeck", "settings.sh")
            if self.kind == "emudeck"
            else self._retrodeck.config_path()
        )

    def config_health(self) -> RetroDeckConfigHealth:
        if self.kind != "emudeck":
            return self._retrodeck.config_health()
        try:
            return RetroDeckConfigHealth.OK if os.path.isdir(self.roms_path()) else RetroDeckConfigHealth.ROOT_MISSING
        except ValueError:
            return RetroDeckConfigHealth.UNREADABLE

    def validate_system(self, system: str) -> None:
        if self.kind != "emudeck":
            return
        if not re.fullmatch(r"[a-z0-9_-]+", system):
            raise ValueError("Invalid EmuDeck system folder")
        root = self.roms_path()
        if root != os.path.realpath(os.path.join(self.retrodeck_home(), "roms")):
            raise ValueError("EmuDeck and ES-DE ROM roots differ; align them before downloading")
        directory = os.path.realpath(os.path.join(root, system))
        if os.path.dirname(directory) != root or not os.path.isdir(directory):
            raise ValueError("Create this system's ROM folder through EmuDeck first")

    def host_command(self, command: str) -> str:
        rules_path = os.path.join(self._home, "ES-DE", "custom_systems", "es_find_rules.xml")
        # Decky does not bundle xml.etree; reuse atlas's expat-backed parser.
        with open(rules_path, encoding="utf-8") as rules_file:
            tree = fromstring(rules_file.read())
        args = shlex.split(command)
        if not args or args[-1] != "%ROM%" or args.count("%ROM%") != 1:
            raise ValueError("This EmuDeck command requires ES-DE launch preparation")
        resolved = []
        for arg in args[:-1]:
            for token in re.findall(r"%([A-Z_]+)%", arg):
                if token.startswith("EMULATOR_"):
                    kind, name, rule = "emulator", token[len("EMULATOR_") :], "staticpath"
                elif token == "CORE_RETROARCH":
                    kind, name, rule = "core", "RETROARCH", "corepath"
                else:
                    raise ValueError("Unsupported ES-DE launch placeholder")
                candidates = [
                    entry
                    for group in tree.findall(kind)
                    if group.get("name") == name
                    for rule_node in group.findall("rule")
                    if rule_node.get("type") == rule
                    for entry in rule_node.findall("entry")
                ]
                paths = [((entry.text or "").strip().replace("~/", self._home + "/", 1)) for entry in candidates]
                path = next(
                    (
                        p
                        for p in paths
                        if os.path.isabs(p)
                        and (os.path.isdir(p) if kind == "core" else os.path.isfile(p) and os.access(p, os.X_OK))
                    ),
                    None,
                )
                if path is None:
                    raise ValueError("The EmuDeck launcher or core directory is unavailable")
                arg = arg.replace("%" + token + "%", path)
            if "%" in arg or arg in (";", "&&", "||", "|", ">", "<", "&"):
                raise ValueError("This EmuDeck command requires a shell or unsupported placeholder")
            resolved.append(arg)
        if not resolved or not os.path.isabs(resolved[0]) or not os.access(resolved[0], os.X_OK):
            raise ValueError("The EmuDeck launch executable is unavailable")
        if "-L" in resolved:
            index = resolved.index("-L")
            if index + 1 == len(resolved) or not os.path.isfile(resolved[index + 1]):
                raise ValueError("The selected EmuDeck RetroArch core is not installed")
        return shlex.join(resolved)


class InstallationCatalogueAdapter:
    def __init__(self, *, catalogue: Any, installation: EmulatorInstallationAdapter) -> None:
        self._catalogue = catalogue
        self._installation = installation

    def __getattr__(self, name: str) -> Any:
        return getattr(self._catalogue, name)

    def get_emulator_options(self, system: str) -> dict[str, Any]:
        result = self._catalogue.get_emulator_options(system)
        if self._installation.kind != "emudeck":
            return result
        options = []
        for option in result["options"]:
            try:
                command = self._installation.host_command(option.command)
                options.append(replace(option, status="bakeable", reason=None, host_command=command))
            except (ValueError, OSError, ParseError):
                options.append(replace(option, status="needs_setup", reason="not_installed"))
        return {**result, "options": options}

    def get_default_emulator(self, system: str) -> EmulatorInvocation | None:
        if self._installation.kind != "emudeck":
            return self._catalogue.get_default_emulator(system)
        selected = select_default_option(self.get_emulator_options(system)["options"])
        return option_to_invocation(selected) if selected else EmulatorInvocation(kind="unavailable")
