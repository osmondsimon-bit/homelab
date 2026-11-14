"""Prove forced-command validation and remote durable dedup using fake probes/jobs."""

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.operations import Plan, PolicyError, Snapshot, plan_digest, plan_to_wire
from codex_messaging.dispatcher import Dispatcher, LiveProber


class Prober:
    def __init__(self):
        self.healthy = False
        self.snapshot_value = Snapshot(
            "node-b", "host", "management", "node-a", "reviewed-1", "before", True,
            impact=("Registered service interruption",), verification=("Application health",),
            preconditions=("identity", "dependency_impact", "application_health"), boot_id="old-boot")
        self.executed = []

    def snapshot(self, target, operation, parameters):
        return self.snapshot_value

    def execute(self, plan):
        self.executed.append(plan)
        self.healthy = True

    def verify(self, plan):
        return self.healthy, "old-boot"

    def diagnostics(self, plan):
        return (("service_state", "inactive"),)


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.prober = Prober()
        self.launches = []
        self.config = {
            "version": 1, "state_dir": self.directory.name, "local_target_id": "node-b",
            "management_target_id": "management", "runbook_version": "reviewed-1",
            "targets": {
                "node-a": {"kind": "host", "machine_id": "a" * 32, "pve_node": "node-a", "vmid": None,
                           "units": [], "operations": ["diagnose"]},
                "node-b": {"kind": "host", "machine_id": "b" * 32, "pve_node": "node-b", "vmid": None,
                           "units": ["example.service"], "operations": ["diagnose", "service_restart"]},
                "management": {"kind": "vm", "machine_id": "c" * 32, "pve_node": None, "vmid": 100,
                               "units": [], "operations": ["diagnose"]},
            },
            "service_policies": {"node-b": {"example.service": {
                "dependency_digest": "d" * 64, "impact": ["Example interruption"],
                "health_url": "https://service.example/health"}}},
        }
        self.active = False
        self.dispatcher = Dispatcher(self.config, prober=self.prober, supervisor=self.launches.append,
                                      job_active=lambda job_id: self.active)
        self.addCleanup(lambda: self.dispatcher.close())

    def request(self):
        plan = Plan("node-b", "host", "service_restart", (("unit", "example.service"),), self.prober.snapshot_value)
        return {"version": 1, "action": "dispatch", "job_id": "1" * 32,
                "plan_digest": plan_digest(plan), "plan": plan_to_wire(plan)}

    def call(self, request, command="codex-messaging-v1"):
        return self.dispatcher.handle(command, json.dumps(request).encode())

    def test_duplicate_delivery_and_duplicate_runner_do_not_repeat_service_restart(self):
        request = self.request()
        self.assertEqual(self.call(request)["result"]["state"], "running")
        self.assertEqual(self.call(request)["result"]["state"], "running")
        self.assertEqual(self.launches, ["1" * 32])
        self.dispatcher.run("1" * 32)
        self.dispatcher.run("1" * 32)
        self.assertEqual(len(self.prober.executed), 1)
        result = self.call({"version": 1, "action": "query", "job_id": "1" * 32})
        self.assertEqual(result["result"]["state"], "verified")

    def test_live_collector_uses_actual_management_host_and_rejects_missing_dependency_proof(self):
        def command(argv, payload=b"", **kwargs):
            if argv[0] == "/usr/bin/pvesh":
                return b'[{"vmid":100,"type":"qemu","node":"node-a","status":"running"}]'
            if "--property=InvocationID" in argv:
                return b"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n"
            return b"Requires=changed.service\n"

        prober = LiveProber(self.config, runner=command,
                            reader=lambda path: "b" * 32 if path == "/etc/machine-id" else "boot-before",
                            health_probe=lambda url: True)
        target = self.dispatcher.registry.resolve("node-b")
        snapshot = prober.snapshot(target, "diagnose", {})
        self.assertEqual(snapshot.management_host_id, "node-a")
        with self.assertRaisesRegex(PolicyError, "preflight_failed"):
            prober.snapshot(target, "service_restart", {"unit": "example.service"})
        with self.assertRaisesRegex(PolicyError, "host_reboot_unproved"):
            prober.snapshot(target, "host_reboot", {})
        with self.assertRaisesRegex(PolicyError, "package_impact_unproved"):
            prober.snapshot(target, "os_maintenance", {})

    def test_wrong_commands_extra_fields_and_changed_replays_never_launch(self):
        request = self.request()
        for command in ("", "sh", "codex-messaging-v1 --shell", "codex-messaging-v1\nwhoami"):
            self.assertFalse(self.call(request, command)["ok"])
        self.assertFalse(self.call(dict(request, shell="PRIVATE_PAYLOAD"))["ok"])
        self.assertEqual(self.launches, [])
        self.call(request)
        changed = self.request()
        changed["plan"]["snapshot"]["plan_version"] = "changed"
        from codex_messaging.operations import plan_from_wire
        changed["plan_digest"] = plan_digest(plan_from_wire(changed["plan"]))
        self.assertEqual(self.call(changed)["error_code"], "job_conflict")
        self.assertEqual(self.launches, ["1" * 32])

    def test_diagnostic_results_are_selected_persisted_fields(self):
        snapshot = replace(self.prober.snapshot_value, preflight_verified=False, preconditions=())
        self.prober.snapshot_value = snapshot
        plan = Plan("node-b", "host", "diagnose", (), snapshot)
        request = {"version": 1, "action": "dispatch", "job_id": "2" * 32,
                   "plan_digest": plan_digest(plan), "plan": plan_to_wire(plan)}
        self.assertTrue(self.call(request)["ok"])
        self.dispatcher.run("2" * 32)
        self.dispatcher.close()
        self.dispatcher = Dispatcher(self.config, prober=self.prober, supervisor=self.launches.append,
                                      job_active=lambda job_id: self.active)
        result = self.call({"version": 1, "action": "query", "job_id": "2" * 32})["result"]
        self.assertEqual(result["diagnostics"], (("service_state", "inactive"),))
        self.assertEqual(len(self.prober.executed), 1)

    def test_live_service_recipe_uses_fixed_argv_and_verifies_a_new_invocation(self):
        dependencies = b"Requires=database.service\n"
        policy = self.config["service_policies"]["node-b"]["example.service"]
        policy["dependency_digest"] = hashlib.sha256(dependencies).hexdigest()
        policy["health_url"] = "http://service.example/health"
        calls, restarted = [], []

        def command(argv, payload=b"", **kwargs):
            calls.append(argv)
            if argv[0] == "/usr/bin/pvesh":
                return b'[{"vmid":100,"type":"qemu","node":"node-a"}]'
            if "restart" in argv:
                restarted.append(True)
                return b""
            if "--property=InvocationID" in argv:
                return ("e" if not restarted else "f").encode() * 32
            return dependencies

        prober = LiveProber(self.config, runner=command,
                            reader=lambda path: "b" * 32 if path == "/etc/machine-id" else "boot-before",
                            health_probe=lambda url: bool(restarted))
        target = self.dispatcher.registry.resolve("node-b")
        snapshot = prober.snapshot(target, "service_restart", {"unit": "example.service"})
        plan = Plan("node-b", "host", "service_restart", (("unit", "example.service"),), snapshot)
        self.assertEqual(prober.verify(plan), (False, "boot-before"))
        prober.execute(plan)
        self.assertEqual(prober.verify(plan), (True, "boot-before"))
        self.assertIn(["/usr/bin/systemctl", "restart", "example.service"], calls)

    def test_lost_supervisor_reply_and_restart_never_launch_a_new_job(self):
        attempts = []

        def lost_reply(job_id):
            attempts.append(job_id)
            raise ConnectionError("PRIVATE_PAYLOAD")

        self.dispatcher.supervisor = lost_reply
        request = self.request()
        self.assertEqual(self.call(request)["result"]["state"], "unknown")
        self.dispatcher.close()
        self.dispatcher = Dispatcher(self.config, prober=self.prober, supervisor=lost_reply,
                                      job_active=lambda job_id: self.active)
        self.assertEqual(self.call(request)["result"]["state"], "unknown")
        self.assertEqual(attempts, ["1" * 32])
        self.assertEqual(self.prober.executed, [])

    def test_runner_rechecks_live_plan_before_any_action(self):
        self.call(self.request())
        self.prober.snapshot_value = replace(self.prober.snapshot_value, plan_version="changed")
        self.dispatcher.run("1" * 32)
        self.assertEqual(self.prober.executed, [])
        self.assertEqual(self.call({"version": 1, "action": "query", "job_id": "1" * 32})["result"]["state"], "failed")

    def test_lxc_mapping_checks_live_type_location_and_guest_machine_identity(self):
        config = json.loads(json.dumps(self.config))
        config["targets"]["container"] = {"kind": "lxc", "machine_id": "c" * 32, "pve_node": None,
                                              "vmid": 123, "units": [], "operations": ["diagnose"]}
        records = [{"vmid": 100, "type": "qemu", "node": "node-a"},
                   {"vmid": 123, "type": "lxc", "node": "node-b", "status": "running"}]
        calls = []

        def command(argv, payload=b"", **kwargs):
            calls.append(argv)
            if argv[0] == "/usr/bin/pvesh":
                return json.dumps(records).encode()
            return b"c" * 32

        prober = LiveProber(config, runner=command,
                            reader=lambda path: "b" * 32 if path == "/etc/machine-id" else "boot-before")
        from codex_messaging.operations import Target
        target = Target("container", "lxc")
        self.assertEqual(prober.snapshot(target, "diagnose", {}).target_kind, "lxc")
        self.assertIn(["/usr/sbin/pct", "exec", "123", "--", "/usr/bin/cat", "/etc/machine-id"], calls)
        records[1]["type"] = "qemu"
        with self.assertRaisesRegex(PolicyError, "identity_changed"):
            prober.snapshot(target, "diagnose", {})

    def test_live_package_action_cannot_be_called_complete_before_its_runner_exits(self):
        request = self.request()
        self.call(request)
        self.prober.healthy = True
        self.active = True
        # The fake target loses its runner response while the active action continues.
        def disconnected(plan):
            raise ConnectionError("PRIVATE_PAYLOAD")
        self.prober.execute = disconnected
        self.dispatcher.run("1" * 32)
        result = self.call({"version": 1, "action": "query", "job_id": "1" * 32})
        self.assertEqual(result["result"]["state"], "running")
        self.active = None
        result = self.call({"version": 1, "action": "query", "job_id": "1" * 32})
        self.assertEqual(result["result"]["state"], "unknown")
        self.active = False
        result = self.call({"version": 1, "action": "query", "job_id": "1" * 32})
        self.assertEqual(result["result"]["state"], "verified")


if __name__ == "__main__":
    unittest.main()
