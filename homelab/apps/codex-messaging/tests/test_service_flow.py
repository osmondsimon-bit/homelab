"""Run the complete relay loop against external HTTP and stdio fixture peers."""

import asyncio
import contextlib
import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.cli import serve
from codex_messaging.transport import Telegram
from test_normal_worker import PEER


class ServiceFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_task_native_approval_and_summary_cross_both_real_transports(self):
        received, complete = [], threading.Event()
        updates = [{"update_id": 1, "message": {"from": {"id": 101}, "chat": {"id": 101, "type": "private"},
                    "text": "Inspect the fixture", "date": int(time.time())}}]
        gate = threading.Lock()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                result = True
                if self.path.endswith("/getUpdates"):
                    time.sleep(0.02)
                    with gate:
                        result = [update for update in updates if update["update_id"] >= body["offset"]]
                elif self.path.endswith("/sendMessage"):
                    with gate:
                        received.append(body)
                        if "reply_markup" in body:
                            data = body["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                            updates.append({"update_id": 2, "callback_query": {"from": {"id": 101},
                                "message": {"chat": {"id": 101, "type": "private"}}, "data": data}})
                        if body["text"] == "Codex finished. No summary was supplied.":
                            complete.set()
                    result = {"message_id": len(received)}
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "result": result}).encode())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            wire = root / "wire.jsonl"
            binary = root / "fixture-codex"
            binary.write_text(f"#!{sys.executable}\nimport sys\nsys.argv=[sys.argv[0],{str(wire)!r},'approval']\n" + PEER)
            binary.chmod(0o700)
            config = {"codex_binary": binary, "bwrap_binary": root / "bwrap", "user_home": root,
                      "workspace": workspace, "state_dir": root}
            with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                client = Telegram("12345:FIXTURE_ONLY_NOT_A_REAL_BOT", fixture_endpoint=f"http://127.0.0.1:{server.server_port}")
                task = asyncio.create_task(serve(config, client, {"user_id": 101, "chat_id": 101, "offset": 0}))
                try:
                    async with asyncio.timeout(8):
                        while not complete.is_set():
                            if task.done():
                                task.result()
                            await asyncio.sleep(0.02)
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                    await asyncio.to_thread(server.shutdown)
                    thread.join(timeout=2)
            records = [json.loads(line) for line in wire.read_text().splitlines()]
            self.assertEqual(sum(item.get("method") == "turn/start" for item in records), 1)
            self.assertIn({"id": "server-command", "result": {"decision": "accept"}}, records)
            self.assertEqual(received[0]["text"], "Working on it.")


if __name__ == "__main__":
    unittest.main()
