"""Check the local operations socket's OS-peer and enrolled-identity boundaries."""

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.ipc import BrokerSocketServer
from codex_messaging.operations import PolicyError
from codex_messaging.transport import BrokerClient


class RecordingOperations:
    def __init__(self):
        self.called = []

    def prepare(self, **arguments):
        self.called.append(arguments)
        return {}

    def resume(self):
        self.called.append("resume")


class SocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_matching_os_peer_cannot_substitute_another_telegram_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broker.sock"
            operations = RecordingOperations()
            server = BrokerSocketServer(path, operations, allowed_uid=os.getuid(), user_id=101, chat_id=101)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(PolicyError) as error:
                    await BrokerClient(str(path)).prepare(202, 101, "guest", "guest_reboot", {})
                self.assertEqual(error.exception.code, "identity_not_allowed")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(operations.called, [])

    async def test_keyless_stage_cannot_enable_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broker.sock"
            operations = RecordingOperations()
            server = BrokerSocketServer(path, operations, allowed_uid=os.getuid(), user_id=101, chat_id=101, allow_changes=False)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(PolicyError) as error:
                    await BrokerClient(str(path)).resume()
                self.assertEqual(error.exception.code, "not_enrolled")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            self.assertEqual(operations.called, [])


if __name__ == "__main__":
    unittest.main()
