"""Exercise packaging failures before an existing release archive is replaced."""

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
try:
    _SPEC = importlib.util.spec_from_file_location("build_plugin_archive", _SCRIPTS / "build_plugin_archive.py")
    assert _SPEC is not None and _SPEC.loader is not None
    _MODULE = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_MODULE)
finally:
    sys.path.pop(0)


class TestBuildPluginArchive(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.destination = self.root / "dist/Tender.zip"
        paths = (
            "LICENSE", "README.md", "main.py", "package.json", "plugin.json", "dist/index.js",
            "bin/rom-launcher", "defaults/config.json", "defaults/README.md",
            "py_modules/bootstrap/__init__.py", "py_modules/bootstrap/adapters.py",
            "py_modules/bootstrap/services.py", "py_modules/db/migrations/001_initial.sql",
            "py_modules/native/libgavel-x86_64-linux.so", "py_modules/_vendor/atlas/__init__.py",
            "py_modules/_vendor/atlas/data/system_ids.json", "py_modules/__pycache__/stale.pyc",
            "py_modules/stale.pyc", "dist/index.js.map",
        )
        for relative in paths:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"name": "Tender"}) if relative == "plugin.json" else relative)
        (self.root / "bin/rom-launcher").chmod(0o755)

    def test_runtime_layout_and_exclusions(self):
        _MODULE.build_archive(self.root, self.destination)
        with zipfile.ZipFile(self.destination) as archive:
            self.assertEqual(archive.read("Tender/config.json"), b"defaults/config.json")
            self.assertEqual(archive.read("Tender/README.md"), b"README.md")
            self.assertFalse(any("__pycache__" in name or name.endswith((".pyc", ".map")) for name in archive.namelist()))
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))

    def test_failed_build_preserves_previous_archive(self):
        self.destination.write_bytes(b"previous archive")
        (self.root / "py_modules/native/libgavel-x86_64-linux.so").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required"):
            _MODULE.build_archive(self.root, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"previous archive")
        self.assertFalse(self.destination.with_suffix(".zip.tmp").exists())

    def test_defaults_collision_is_rejected(self):
        (self.root / "defaults/plugin.json").write_text("duplicate")
        with self.assertRaisesRegex(ValueError, "collide"):
            _MODULE.build_archive(self.root, self.destination)

    def test_symlink_is_not_followed(self):
        (self.root / "py_modules/linked").symlink_to(self.root / "defaults", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            _MODULE.build_archive(self.root, self.destination)


if __name__ == "__main__":
    unittest.main()
