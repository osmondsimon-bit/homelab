"""Ensure Telegram presentation cannot accidentally stream common diagnostic secrets."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.presentation import safe_text


class PresentationTests(unittest.TestCase):
    def test_private_looking_diagnostics_are_replaced_with_a_local_detail_notice(self):
        for text in ["Connect to 192.0.2.23", "Connect to 2001:db8::1", "Device " + ":".join(["02"] + ["00"] * 4 + ["01"]),
                     "Key sk-" + "x" * 32, "Read /home/operator/.ssh/key", "See https://internal.invalid/status"]:
            with self.subTest(text=text):
                self.assertEqual(safe_text(text), "Details are available locally.")

    def test_short_plain_results_can_be_presented(self):
        self.assertEqual(safe_text("Jellyfin is healthy."), "Jellyfin is healthy.")

    def test_the_bot_does_not_solicit_login_secrets(self):
        self.assertEqual(safe_text("Please enter your password to continue."), "Details are available locally.")


if __name__ == "__main__":
    unittest.main()
