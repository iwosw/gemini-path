import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_route as route


class BrowserRouteTests(unittest.TestCase):
    def test_resolver_rules_only_affect_selected_google_hosts(self):
        rules = route.resolver_rules("45.88.174.254")
        self.assertEqual(rules, "MAP gemini.google.com 45.88.174.254,MAP accounts.google.com 45.88.174.254")
        self.assertNotIn("www.google.com", rules)
        with self.assertRaises(ValueError):
            route.resolver_rules("not an IP")

    def test_browser_launch_is_isolated_and_has_no_direct_fallback_for_mapped_hosts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            browser = Path(folder) / "chrome.exe"
            browser.touch()
            with patch.object(route, "check_gateway", return_value=route.GATEWAY), \
                 patch.object(route.subprocess, "Popen") as spawn, \
                 patch.dict(os.environ, {"LOCALAPPDATA": folder}):
                route.open_site(browser=browser)
            command = spawn.call_args.args[0]
            self.assertIn("--disable-quic", command)
            self.assertIn("--no-proxy-server", command)
            self.assertIn("--user-data-dir=" + str(Path(folder) / "GeminiPath" / "browser-profile"), command)
            self.assertIn("--host-resolver-rules=" + route.resolver_rules(), command)
            self.assertNotIn("--no-check-certificate", command)
            self.assertEqual(command[-1], "https://gemini.google.com/app")

    def test_probe_failure_does_not_launch_or_change_browser_profile(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(route, "check_gateway", side_effect=TimeoutError("relay unavailable")), \
                 patch.object(route.subprocess, "Popen") as spawn, \
                 patch.dict(os.environ, {"LOCALAPPDATA": folder}):
                with self.assertRaises(TimeoutError):
                    route.open_site()
            spawn.assert_not_called()
            self.assertFalse((Path(folder) / "GeminiPath" / "browser-profile").exists())


if __name__ == "__main__":
    unittest.main()
