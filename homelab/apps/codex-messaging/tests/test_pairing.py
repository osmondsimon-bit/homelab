"""Exercise console-to-private-chat enrollment without a real Telegram account."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.cli import pair


class PairingTests(unittest.IsolatedAsyncioTestCase):
    async def test_pairing_requires_fresh_console_nonce_and_private_human_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "enrollment.json"
            announced = []

            class TelegramFixture:
                def get_updates(self, offset):
                    phrase = announced[0].split("Send ", 1)[1].split(" in a private", 1)[0]
                    def message(identifier, text, kind="private", stamp=1000, bot=False):
                        return {"update_id": identifier, "message": {"text": text, "date": stamp,
                            "from": {"id": 101, "is_bot": bot}, "chat": {"id": 101, "type": kind}}}
                    return [message(1, "/start"), message(2, phrase, "group"), message(3, phrase, stamp=0),
                            message(4, phrase, bot=True), message(5, phrase)]

            await pair(TelegramFixture(), destination, announce=announced.append, clock=lambda: 1000)
            owner = json.loads(destination.read_text())
            self.assertEqual((owner["user_id"], owner["chat_id"], owner["offset"]), (101, 101, 6))
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(announced), 2)


if __name__ == "__main__":
    unittest.main()
