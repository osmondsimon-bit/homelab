"""Verify graceful application-LXC lifecycle policy using fake vendor probes."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import fcntl
import stat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.operations import Plan, PolicyError, Target
from codex_messaging.lxc_reboot import ApplicationLXCReboot, NATIVE_FILES, pve_config_lock


class LXCRebootTests(unittest.TestCase):
    def setUp(self):
        self.target = Target("application", "lxc", units=("example.service",), operations=("guest_reboot",))
        self.pid, self.ticks, self.parent_boot, self.healthy, self.held = 200, 1000, "parent-before", True, False
        self.actions = []
        self.current = {"onboot": 1, "digest": "a" * 40}
        self.pending, self.ha, self.signal = [], [], "SIGINT"
        self.dropins, self.fail_action = "", False
        self.native = {path: ("reviewed fixture " + path).encode() for path in NATIVE_FILES}
        fingerprint = hashlib.sha256(json.dumps({path: hashlib.sha256(value).hexdigest() for path, value in self.native.items()},
                                               sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.config = {"local_target_id": "node-b", "management_target_id": "management", "runbook_version": "reviewed-1",
                       "targets": {"node-b": {"kind": "host", "pve_node": "node-b"},
                                   "application": {"kind": "lxc", "vmid": 123, "machine_id": "b" * 32, "units": ["example.service"]}},
                       "service_policies": {"application": {"example.service": {"health_url": "http://application.example/health"}}},
                       "reboot_policies": {"application": {"role": "application", "control_dependencies": [],
                                                           "required_units": ["example.service"], "shutdown_timeout": 60,
                                                           "native_contract_digest": fingerprint}}}
        self.adapter = ApplicationLXCReboot(self.config, command=self.command, reader=self.reader,
                                            native_reader=self.native.__getitem__, native_inventory=lambda: tuple(self.native),
                                            identity=lambda target: ("node-a", "shared-kernel"),
                                            health_probe=lambda url: self.healthy, config_lock=self.lock)

    @contextmanager
    def lock(self, vmid):
        self.assertEqual(vmid, 123)
        self.assertFalse(self.held)
        self.held = True
        try:
            yield
        finally:
            self.held = False

    def reader(self, path):
        if path == "/proc/sys/kernel/random/boot_id":
            return self.parent_boot
        self.assertEqual(path, f"/proc/{self.pid}/stat")
        return str(self.pid) + " (guest init)) S " + "0 " * 18 + str(self.ticks)

    def command(self, argv, payload=b"", **kwargs):
        self.assertTrue(self.held)
        if argv[0] == "/usr/bin/lxc-stop":
            self.actions.append(argv)
            if self.fail_action:
                raise PolicyError("command_unavailable")
            self.pid, self.ticks = 300, 2000
            return b""
        if argv[0] == "/usr/bin/lxc-info":
            if "-c" in argv and "lxc.signal.reboot" not in argv:
                return b""
            return (str(self.pid) if "-p" in argv else self.signal).encode()
        if argv[0] == "/usr/bin/pvesh":
            path = argv[2]
            if path == "/cluster/status":
                return b'[{"type":"cluster","quorate":1}]'
            if path == "/cluster/ha/resources":
                return json.dumps(self.ha).encode()
            if path.endswith("/pending"):
                return json.dumps(self.pending).encode()
            if path.endswith("/config"):
                return json.dumps(self.current).encode()
            return b'{"vmid":123,"status":"running","ha":{"managed":0}}'
        if argv[0] == "/usr/sbin/pct":
            return b"ActiveState=active\nUnitFileState=enabled\n"
        return ("FragmentPath=/usr/lib/systemd/system/pve-container@.service\nDropInPaths=" + self.dropins + "\n").encode()

    def test_reboot_uses_nokill_and_proves_a_new_container_instance_on_the_same_parent(self):
        snapshot = self.adapter.snapshot(self.target)
        self.assertEqual(snapshot.parent_boot_id, "parent-before")
        plan = Plan("application", "lxc", "guest_reboot", (), snapshot)
        self.assertFalse(self.adapter.verify(plan)[0])
        self.adapter.execute(plan)
        healthy, boot = self.adapter.verify(plan)
        self.assertTrue(healthy)
        self.assertNotEqual(boot, snapshot.boot_id)
        self.assertEqual(self.actions, [["/usr/bin/lxc-stop", "-n", "123", "--reboot", "--nokill", "--timeout", "60"]])

    def test_parent_reboot_unhealthy_app_and_unchanged_instance_cannot_be_success(self):
        snapshot = self.adapter.snapshot(self.target)
        plan = Plan("application", "lxc", "guest_reboot", (), snapshot)
        self.assertFalse(self.adapter.verify(plan)[0])
        self.pid, self.ticks = 300, 2000
        self.parent_boot = "parent-changed"
        self.assertFalse(self.adapter.verify(plan)[0])
        self.parent_boot, self.healthy = "parent-before", False
        self.assertFalse(self.adapter.verify(plan)[0])
        self.healthy = True
        self.assertTrue(self.adapter.verify(plan)[0])

    def test_pending_managed_control_or_custom_lifecycle_state_is_unavailable(self):
        cases = [
            ("current", {"onboot": 0, "digest": "a" * 40}),
            ("current", {"onboot": 1, "digest": "a" * 40, "hookscript": "unreviewed"}),
            ("current", {"onboot": 1, "digest": "a" * 40, "lock": "backup"}),
            ("current", {"onboot": 1, "digest": "a" * 40, "lxc": [["lxc.include", "unreviewed"]]}),
            ("pending", [{"key": "memory", "pending": 2048}]),
            ("ha", [{"sid": "ct:123", "state": "ignored"}]),
            ("signal", "SIGKILL"), ("dropins", "/etc/systemd/system/unreviewed.conf"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                before = getattr(self, field)
                setattr(self, field, value)
                with self.assertRaises(PolicyError):
                    self.adapter.snapshot(self.target)
                setattr(self, field, before)
        policy = self.config["reboot_policies"]["application"]
        for field, value in [("role", "control_plane"), ("control_dependencies", ["management"])]:
            before = policy[field]
            policy[field] = value
            with self.assertRaisesRegex(PolicyError, "guest_verification_unproved"):
                self.adapter.snapshot(self.target)
            policy[field] = before
        self.native[NATIVE_FILES[0]] = b"unreviewed release"
        with self.assertRaisesRegex(PolicyError, "guest_verification_unproved"):
            self.adapter.snapshot(self.target)
        self.assertEqual(self.actions, [])

    def test_changed_plan_and_graceful_timeout_never_add_a_force_or_restart_fallback(self):
        snapshot = self.adapter.snapshot(self.target)
        plan = Plan("application", "lxc", "guest_reboot", (), snapshot)
        self.current["digest"] = "f" * 40
        with self.assertRaisesRegex(PolicyError, "plan_changed"):
            self.adapter.execute(plan)
        self.assertEqual(self.actions, [])
        self.current["digest"] = "a" * 40
        self.fail_action = True
        with self.assertRaisesRegex(PolicyError, "command_unavailable"):
            self.adapter.execute(plan)
        self.assertEqual(len(self.actions), 1)
        self.assertIn("--nokill", self.actions[0])
        self.assertFalse(self.adapter.verify(plan)[0])

    def test_lock_boundary_matches_the_vendor_path_and_exclusive_flock_contract(self):
        directory = SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755)
        file = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644, st_nlink=1)
        with patch("codex_messaging.lxc_reboot.os.open", side_effect=[10, 11]) as opening, \
                patch("codex_messaging.lxc_reboot.os.fstat", side_effect=[directory, file]), \
                patch("codex_messaging.lxc_reboot.os.close") as closing, \
                patch("codex_messaging.lxc_reboot.fcntl.flock") as lock:
            with pve_config_lock(123):
                lock.assert_called_once_with(11, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertFalse(closing.called)
            self.assertEqual(opening.call_args_list[0].args[0], "/run/lock/lxc")
            self.assertEqual(opening.call_args_list[1].args[0], "pve-config-123.lock")
            self.assertEqual(opening.call_args_list[1].kwargs, {"dir_fd": 10})
            self.assertEqual([call.args for call in closing.call_args_list], [(11,), (10,)])


if __name__ == "__main__":
    unittest.main()
