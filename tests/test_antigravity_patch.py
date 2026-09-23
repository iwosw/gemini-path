import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import antigravity_patch as tool


def fixture(signature=b"\x80\x78\x08\x00\x74\x0a\x48\x8b\x44\x24\x20\x48\x89\x44\x60"):
    data = bytearray(1536)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HH", data, 132, 0x8664, 1)
    struct.pack_into("<H", data, 148, 240)
    data[392:400] = b".text\0\0\0"
    struct.pack_into("<II", data, 408, 512, 512)
    data[512:512 + len(signature)] = signature
    return bytes(data)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "language_server.exe"
        self.state = self.root / "state"
        self.original = fixture()
        self.target.write_bytes(self.original)
        running = patch.object(tool, "app_running", return_value=False)
        running.start()
        self.addCleanup(running.stop)

    def test_patching_restores_exact_original_and_keeps_backup(self):
        original_hash = tool.sha256(self.original)
        record = tool.patch_file(self.target, self.state)
        self.assertEqual(record["original_sha256"], original_hash)
        self.assertEqual(tool.inspect(self.target.read_bytes())[0], "patched")
        self.assertEqual((self.state / f"{original_hash}.bin").read_bytes(), self.original)
        self.assertEqual(json.loads((self.state / "antigravity.json").read_text())["target"], str(self.target.resolve()))
        self.assertEqual(tool.restore_file(self.target, self.state), "restored")
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse((self.state / "antigravity.json").exists())

    def test_refuses_to_overwrite_updated_executable(self):
        tool.patch_file(self.target, self.state)
        edited = self.target.read_bytes() + b"new version"
        self.target.write_bytes(edited)
        with self.assertRaisesRegex(ValueError, "updated or edited"):
            tool.restore_file(self.target, self.state)
        self.assertEqual(self.target.read_bytes(), edited)

    def test_updated_stock_executable_is_not_replaced_with_old_backup(self):
        tool.patch_file(self.target, self.state)
        newer = self.original + b"updated"
        self.target.write_bytes(newer)
        self.assertIn("updated itself", tool.restore_file(self.target, self.state))
        self.assertEqual(self.target.read_bytes(), newer)
        self.assertFalse((self.state / "antigravity.json").exists())

    def test_refuses_unknown_or_ambiguous_pattern(self):
        duplicated = bytearray(fixture())
        duplicated[600:615] = self.original[512:527]
        for content in (fixture(b"unrecognized"), fixture()[:100], bytes(duplicated)):
            self.target.write_bytes(content)
            with self.assertRaises(ValueError):
                tool.patch_file(self.target, self.state)
            self.assertFalse((self.state / "antigravity.json").exists())

    @unittest.skipUnless(os.environ.get("GEMINIPATH_REAL_APP_TEST"), "opt-in real image copy")
    def test_unmodified_installed_image_copy_round_trip(self):
        source = tool.default_target()
        if not source.is_file():
            self.skipTest("Antigravity is not installed")
        shutil.copy2(source, self.target)
        real_original = self.target.read_bytes()
        self.assertEqual(tool.inspect(real_original)[0], "stock")
        tool.patch_file(self.target, self.state)
        self.assertEqual(tool.inspect(self.target.read_bytes())[0], "patched")
        self.assertEqual(tool.restore_file(self.target, self.state), "restored")
        self.assertEqual(self.target.read_bytes(), real_original)


if __name__ == "__main__":
    unittest.main()
