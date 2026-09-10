"""Reject packages that build successfully but cannot be installed or launched."""

import importlib.util
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_plugin_archive.py"
_SPEC = importlib.util.spec_from_file_location("check_plugin_archive", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_PAYLOAD = (
    "main.py", "plugin.json", "package.json", "dist/index.js", "bin/rom-launcher",
    "config.json", "py_modules/bootstrap/__init__.py",
    "py_modules/bootstrap/adapters.py", "py_modules/bootstrap/services.py",
    "py_modules/db/migrations/001_initial.sql", "py_modules/native/libgavel-x86_64-linux.so",
    "py_modules/_vendor/atlas/__init__.py", "py_modules/_vendor/atlas/data/system_ids.json",
)


class TestPluginArchive(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.archive = Path(self.directory.name) / "Tender.zip"

    def package(self, *, omitted=None, extra=None, launcher_mode=0o100755, empty=None, name="Tender"):
        with zipfile.ZipFile(self.archive, "w") as bundle:
            for path in _PAYLOAD:
                if path == omitted:
                    continue
                entry = zipfile.ZipInfo(f"Tender/{path}")
                entry.create_system = 3
                mode = launcher_mode if path == "bin/rom-launcher" else 0o100644
                entry.external_attr = mode << 16
                data = json.dumps({"name": name}) if path == "plugin.json" else "payload"
                bundle.writestr(entry, "" if path == empty else data)
            if extra:
                bundle.writestr(extra, "unexpected")

    def test_complete_package(self):
        self.package()
        _MODULE.validate_archive(self.archive)

    def test_missing_runtime_payload(self):
        for path in ("py_modules/db/migrations/001_initial.sql", "py_modules/native/libgavel-x86_64-linux.so"):
            with self.subTest(path=path):
                self.package(omitted=path)
                with self.assertRaisesRegex(ValueError, "Missing required entries"):
                    _MODULE.validate_archive(self.archive)

    def test_non_executable_launcher(self):
        self.package(launcher_mode=0o100644)
        with self.assertRaisesRegex(ValueError, "not executable"):
            _MODULE.validate_archive(self.archive)

    def test_symlink_launcher(self):
        self.package(launcher_mode=stat.S_IFLNK | 0o777)
        with self.assertRaisesRegex(ValueError, "symlink"):
            _MODULE.validate_archive(self.archive)

    def test_empty_frontend_bundle(self):
        self.package(empty="dist/index.js")
        with self.assertRaisesRegex(ValueError, "Missing payload"):
            _MODULE.validate_archive(self.archive)

    def test_source_maps(self):
        self.package(extra="Tender/dist/index.js.map")
        with self.assertRaisesRegex(ValueError, "source maps"):
            _MODULE.validate_archive(self.archive)

    def test_unsafe_paths(self):
        for path in ("../escape", "/absolute", "Tender/../escape"):
            with self.subTest(path=path):
                self.package(extra=path)
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    _MODULE.validate_archive(self.archive)

    def test_multiple_roots(self):
        self.package(extra="Other/main.py")
        with self.assertRaisesRegex(ValueError, "one plugin directory"):
            _MODULE.validate_archive(self.archive)

    def test_wrong_plugin_identity(self):
        self.package(name="Wrong")
        with self.assertRaisesRegex(ValueError, "identify itself as Tender"):
            _MODULE.validate_archive(self.archive)


if __name__ == "__main__":
    unittest.main()
