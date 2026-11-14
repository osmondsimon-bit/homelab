"""Verify the first commissioning stage cannot acquire operational authority."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.configuration import ConfigurationRejected, keyless_settings


class ConfigurationTests(unittest.TestCase):
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
