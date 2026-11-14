"""Check fixed SSH transport, closed wire protocol and durable job routing offline."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.operations import Plan, PolicyError, RemoteResult, Snapshot, Target, plan_digest
from codex_messaging.remote import SSHRemoteAdapter, run_bounded


class SSHTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.calls = []
        self.snapshot = Snapshot("guest", "vm", "management", "node-a", "reviewed-1", "plan-1", True)
        self.response = {"version": 1, "ok": True, "result": asdict(self.snapshot)}
        self.config = {"version": 1, "identity_file": "/fixture/identity", "known_hosts": "/fixture/hosts",
                       "routing_db": str(Path(self.directory.name) / "routing.sqlite"),
                       "targets": {"guest": {"host": "registered.example", "user": "operator", "port": 22}}}
        self.adapter = SSHRemoteAdapter(self.config, runner=self.run_command)
        self.addCleanup(lambda: self.adapter.close())

    def run_command(self, argv, payload, *, timeout, limit):
        self.calls.append((argv, json.loads(payload), timeout, limit))
        return json.dumps(self.response).encode()

    def test_inspect_uses_only_fixed_ssh_configuration_and_registered_endpoint(self):
        result = self.adapter.inspect(Target("guest", "vm"), "diagnose", {})
        self.assertEqual(result.target_id, "guest")
        argv, request, _, _ = self.calls[0]
        self.assertEqual(argv[-2:], ["registered.example", "codex-messaging-v1"])
        self.assertIn("IdentityAgent=none", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("ProxyCommand=none", argv)
        self.assertIn("ClearAllForwardings=yes", argv)
        self.assertEqual(request, {"version": 1, "action": "inspect", "target_id": "guest",
                                   "operation": "diagnose", "parameters": {}})

    def test_job_routing_survives_restart_and_query_never_dispatches(self):
        plan = Plan("guest", "vm", "diagnose", (), self.snapshot)
        self.response = {"version": 1, "ok": True, "result": asdict(RemoteResult("running"))}
        self.adapter.dispatch("a" * 32, plan)
        self.adapter.close()
        self.adapter = SSHRemoteAdapter(self.config, runner=self.run_command)
        self.adapter.query("a" * 32)
        self.assertEqual([request[1]["action"] for request in self.calls], ["dispatch", "query"])
        self.assertEqual(self.calls[-1][1]["job_id"], "a" * 32)

    def test_unknown_targets_malformed_responses_and_remote_errors_do_not_echo_payloads(self):
        with self.assertRaisesRegex(PolicyError, "target_unknown"):
            self.adapter.inspect(Target("unregistered", "vm"), "diagnose", {})
        self.response = {"version": 1, "ok": False, "error_code": "PRIVATE_ENDPOINT_CREDENTIAL"}
        with self.assertRaisesRegex(PolicyError, "remote_rejected"):
            self.adapter.inspect(Target("guest", "vm"), "diagnose", {})
        self.response = {"version": 1, "ok": True, "result": {}, "extra": "PRIVATE_ENDPOINT_CREDENTIAL"}
        with self.assertRaisesRegex(PolicyError, "wire_invalid"):
            self.adapter.inspect(Target("guest", "vm"), "diagnose", {})

    def test_process_boundary_drops_inherited_credentials_and_bounds_output(self):
        os.environ["CODEX_TEST_PRIVATE_SECRET"] = "private sentinel"
        self.addCleanup(os.environ.pop, "CODEX_TEST_PRIVATE_SECRET", None)
        output = run_bounded([sys.executable, "-I", "-c", "import os,json; print(json.dumps(dict(os.environ)))"], timeout=2)
        self.assertNotIn("CODEX_TEST_PRIVATE_SECRET", json.loads(output))
        for script, timeout, limit in [("print('x'*4096)", 2, 128), ("import time;time.sleep(1)", 0.05, 128)]:
            with self.subTest(script=script):
                with self.assertRaisesRegex(PolicyError, "command_unavailable"):
                    run_bounded([sys.executable, "-I", "-c", script], timeout=timeout, limit=limit)

    def test_noninteger_protocol_versions_and_forged_job_ids_are_rejected(self):
        self.response["version"] = True
        with self.assertRaisesRegex(PolicyError, "wire_invalid"):
            self.adapter.inspect(Target("guest", "vm"), "diagnose", {})
        with self.assertRaisesRegex(PolicyError, "request_invalid"):
            self.adapter.query("; PRIVATE_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
