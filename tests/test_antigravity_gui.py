from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import antigravity_gui as gui
from test_antigravity_patch import fixture


class GuiTests(unittest.TestCase):
    def test_missing_file_disables_changes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            state, record = gui.state_for_target(Path(folder) / "language_server.exe", Path(folder))
            self.assertEqual((state, record), ("missing", False))
            self.assertEqual(gui.display_state(state, record)[2:], (False, False))

    def test_scan_and_failed_patch_keep_recovery_controls(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk display is unavailable")
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            target = Path(folder) / "language_server.exe"
            target.write_bytes(fixture())
            with patch.object(gui.patcher, "default_target", return_value=target), \
                 patch.object(gui, "STATE_DIR", Path(folder) / "patches"):
                window = gui.PatcherWindow(root)
                self._wait(root, window)
                self.assertEqual(window.patch_button.cget("state"), "normal")
                with patch.object(gui.patcher, "patch_file", side_effect=ValueError("close app")):
                    window.run("patch")
                    self._wait(root, window)
                self.assertIn("close app", window.log.get("1.0", "end"))
                self.assertEqual(window.patch_button.cget("state"), "normal")
                self.assertEqual(target.read_bytes(), fixture())
                with patch.object(gui.browser_route, "open_site", return_value="Отдельный браузер открыт"):
                    window.run("browser")
                    self._wait(root, window)
                self.assertIn("Отдельный браузер открыт", window.log.get("1.0", "end"))

    @staticmethod
    def _wait(root, window):
        deadline = time.monotonic() + 8
        while window.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        root.update()
        if window.busy:
            raise AssertionError("GUI operation did not finish")


if __name__ == "__main__":
    unittest.main()
