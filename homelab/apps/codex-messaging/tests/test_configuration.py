"""Verify the first commissioning stage cannot acquire operational authority."""

import sys
import contextlib
import io
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.configuration import ConfigurationRejected, keyless_settings


class ConfigurationTests(unittest.TestCase):
    def test_unresolved_runtime_advisories_block_all_real_account_entry_points(self):
        from codex_messaging.cli import main
        for command in ("gateway", "worker", "worker-login"):
            with self.subTest(command=command):
                output = io.StringIO()
                with contextlib.redirect_stderr(output):
                    result = main([command])
                self.assertEqual(result, 1)
                self.assertEqual(output.getvalue().strip(), "runtime_security_review_required")

    def test_keyless_settings_reject_keys_endpoints_and_operational_mode(self):
        base = {"version": 1, "mode": "keyless", "user_id": 101, "chat_id": 101}
        self.assertEqual(keyless_settings(base)["mode"], "keyless")
        for extra in [{"mode": "operational"}, {"ssh_key": "/fixture/key"},
                      {"api_key": "fixture"}, {"telegram_endpoint": "https://fixture.invalid"},
                      {"user_id": True}, {"chat_id": -1}]:
            with self.subTest(extra=extra), self.assertRaises(ConfigurationRejected):
                keyless_settings(base | extra)


if __name__ == "__main__":
    unittest.main()
