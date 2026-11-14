"""Verify useful phone summaries and approval text omit addresses and credentials."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.presentation import LOCAL_NOTICE, phone_text, safe_text


class PresentationTests(unittest.TestCase):
    def test_phone_text_redacts_values_without_hiding_normal_commands(self):
        text = phone_text('ssh root@192.0.2.23 "systemctl restart jellyfin"', home=Path('/home/operator'))
        self.assertIn('systemctl restart jellyfin', text)
        self.assertIn('[address]', text)
        self.assertNotIn('192.0.2.23', text)
        self.assertEqual(phone_text('Edit /home/operator/homelab/PLAN.md', home=Path('/home/operator')), 'Edit ~/homelab/PLAN.md')
        self.assertEqual(safe_text(text), text)

    def test_credentials_and_private_keys_never_appear_in_phone_output(self):
        for raw in ['sk-' + 'a' * 40, '12345:' + 'b' * 35, 'Authorization: Bearer secret-value', 'password=secret-value']:
            with self.subTest(kind=raw[:3]):
                self.assertNotIn(raw, phone_text('Result: ' + raw))
        self.assertEqual(phone_text('-----BEGIN PRIVATE KEY-----\nsynthetic'), LOCAL_NOTICE)
        self.assertEqual(safe_text('192.0.2.23'), LOCAL_NOTICE)

    def test_regular_paths_urls_and_password_manager_status_are_useful(self):
        text = 'Password manager healthy; reviewed /etc/systemd/system/example.service'
        self.assertEqual(phone_text(text), text)
        self.assertEqual(phone_text('See https://github.com/example/project'), 'See https://github.com/example/project')
        self.assertEqual(phone_text('Please enter your password to continue.'), LOCAL_NOTICE)


if __name__ == '__main__':
    unittest.main()
