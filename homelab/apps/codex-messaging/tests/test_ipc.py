"""Check the local operations socket's OS-peer and enrolled-identity boundaries."""

import os
import socket
import queue
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.ipc import BrokerSocketServer
from codex_messaging.operations import Job, PolicyError
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
    async def test_stalled_connections_have_a_bounded_concurrency_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broker.sock"
            entered, release = queue.Queue(), threading.Event()
            operations = RecordingOperations()
            def held_status(**arguments):
                entered.put(None)
                release.wait(5)
                return Job("fixture", "failed", None, "a" * 64, "guest", "service_restart")
            operations.status = held_status
            server = BrokerSocketServer(path, operations, allowed_uid=os.getuid(), user_id=101, chat_id=101)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            clients = []
            try:
                for _ in range(16):
                    client = socket.socket(socket.AF_UNIX)
                    clients.append(client)
                    client.settimeout(2)
                    client.connect(str(path))
                    client.sendall(json.dumps({"version": 1, "method": "status", "arguments": {"job_id": "fixture"}}).encode() + b"\n")
                    entered.get(timeout=2)
                extra = socket.socket(socket.AF_UNIX)
                clients.append(extra)
                extra.settimeout(2)
                extra.connect(str(path))
                self.assertEqual(extra.recv(1), b"")
            finally:
                release.set()
                for client in clients:
                    client.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

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
