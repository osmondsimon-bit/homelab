"""Check external messaging requests without a real bot or external network service."""

import http.server
import json
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.transport import Telegram, TransportRejected


class TelegramTests(unittest.TestCase):
    def test_updates_use_only_the_expected_api_method_and_never_echo_tokens(self):
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true,"result":[{"update_id":12}]}')

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = Telegram("12345:FIXTURE_ONLY_NOT_A_REAL_BOT", fixture_endpoint=f"http://127.0.0.1:{server.server_port}")
                self.assertEqual(client.get_updates(12), [{"update_id": 12}])
            finally:
                server.shutdown()
                thread.join(timeout=2)
        self.assertTrue(received[0][0].endswith("/getUpdates"))
        self.assertEqual(received[0][1]["allowed_updates"], ["message", "callback_query"])
        with self.assertRaises(TransportRejected) as error:
            Telegram("not-a-token")
        self.assertNotIn("not-a-token", str(error.exception))


if __name__ == "__main__":
    unittest.main()
