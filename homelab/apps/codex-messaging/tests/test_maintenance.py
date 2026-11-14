"""Prove constrained apt parsing, policy and original-job execution offline."""

from pathlib import Path
import tempfile
import hashlib
import json
import sys
import unittest
from unittest.mock import patch
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.operations import Plan, Snapshot, PackageChange, PolicyError
from codex_messaging.maintenance import AptMaintenance, GuardJournal, archive_metadata, parse_simulation, run_package, validate_origins


SIMULATION = """Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
The following additional packages will be installed:
  libexample1
The following NEW packages will be installed:
  libexample1
The following packages will be upgraded:
  bash
1 upgraded, 1 newly installed, 0 to remove and 3 not upgraded.
Inst bash [5.2-1] (5.2-2 Debian:12/stable [amd64])
Inst libexample1 (1.0-1 Debian:12/stable [amd64])
Conf bash (5.2-2 Debian:12/stable [amd64])
Conf libexample1 (1.0-1 Debian:12/stable [amd64])
"""


class SimulationTests(unittest.TestCase):
    def test_simulation_identifies_exact_install_and_upgrade_versions(self):
        changes = parse_simulation(SIMULATION.encode())
        self.assertEqual([(p.name, p.current, p.candidate, p.action) for p in changes],
                         [("bash", "5.2-1", "5.2-2", "upgrade"), ("libexample1", "", "1.0-1", "install")])

    def test_removals_ambiguous_lines_partial_output_and_prompts_are_rejected(self):
        for payload in [
            SIMULATION + "Remv example [1.0]\n", SIMULATION + "Purg example\n",
            SIMULATION + "Do you want to continue? [Y/n]\n", SIMULATION + "Inst bash [5.2-1] (5.2-2 Debian [amd64])\n",
            SIMULATION.replace("Conf bash (5.2-2 Debian:12/stable [amd64])\n", ""),
            SIMULATION.replace("0 to remove", "1 to remove"),
            SIMULATION.replace("Inst libexample1", "Inst /tmp/package"),
        ]:
            with self.subTest(payload=payload[-80:]):
                with self.assertRaisesRegex(PolicyError, "package_plan_unsafe"):
                    parse_simulation(payload.encode())

    def test_candidate_requires_every_possible_source_to_match_trusted_os_policy(self):
        changes = parse_simulation(SIMULATION.encode())
        indexes = b"""Identifier: Packages
Description: https://archive.example/debian stable/main amd64 Packages
Origin: Debian
Codename: stable
Component: main
Architecture: amd64
Trusted: yes
"""
        policies = {
            "bash": """bash:
  Installed: 5.2-1
  Candidate: 5.2-2
  Version table:
     5.2-2 500
        500 https://archive.example/debian stable/main amd64 Packages
 *** 5.2-1 100
        100 /var/lib/dpkg/status
""",
            "libexample1": """libexample1:
  Installed: (none)
  Candidate: 1.0-1
  Version table:
     1.0-1 500
        500 https://archive.example/debian stable/main amd64 Packages
""",
        }
        policy = {"reviewed_os_packages": ["bash", "libexample1"], "allowed_origins": ["Debian"],
                  "allowed_codenames": ["stable"], "denied_packages": []}
        self.assertEqual(validate_origins(changes, indexes, policies, policy), (("bash", "amd64"), ("libexample1", "amd64")))
        for bad_indexes, bad_policy in [
            (indexes.replace(b"Trusted: yes", b"Trusted: no"), policy),
            (indexes.replace(b"Origin: Debian", b"Origin: ThirdParty"), policy),
            (indexes, dict(policy, reviewed_os_packages=["bash"])),
            (indexes, dict(policy, denied_packages=["bash"])),
        ]:
            with self.subTest(policy=bad_policy, indexes=bad_indexes):
                with self.assertRaisesRegex(PolicyError, "package_origin_unsafe"):
                    validate_origins(changes, bad_indexes, policies, bad_policy)
        protected = {"openssh-server": policies["bash"].replace("bash:", "openssh-server:")}
        with self.assertRaisesRegex(PolicyError, "package_origin_unsafe"):
            validate_origins((PackageChange("openssh-server", "5.2-1", "5.2-2"),), indexes, protected,
                             dict(policy, reviewed_os_packages=["openssh-server"]))


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.context = {"version": 1, "job_id": "a" * 32, "target_id": "guest", "machine_id": "b" * 32,
                        "boot_id": "boot-before", "runbook_version": "reviewed-1", "transaction_digest": "c" * 64,
                        "apt_configuration_digest": "d" * 64, "guard_digest": "e" * 64,
                        "packages": [["bash", "5.2-2", "amd64"]]}
        self.archives = {"/var/cache/apt/archives/bash_5.2-2_amd64.deb": ("bash", "5.2-2", "amd64")}
        self.guard = GuardJournal(self.directory.name, artifact_reader=self.archives.__getitem__,
                                  machine_reader=lambda: ("b" * 32, "boot-before"),
                                  configuration_reader=lambda: "d" * 64, digest_reader=lambda: "e" * 64,
                                  audit_reader=lambda: b"")
        self.addCleanup(self.guard.close)

    def test_exact_archive_transaction_is_one_use_and_changed_context_cannot_replace_it(self):
        self.guard.prepare("a" * 32, self.context)
        self.guard.prepare("a" * 32, self.context)
        self.guard.verify("a" * 32, b"/var/cache/apt/archives/bash_5.2-2_amd64.deb\n")
        with self.assertRaisesRegex(PolicyError, "job_conflict"):
            self.guard.prepare("a" * 32, self.context)
        with self.assertRaisesRegex(PolicyError, "job_conflict"):
            self.guard.verify("a" * 32, b"/var/cache/apt/archives/bash_5.2-2_amd64.deb\n")

    def test_arbitrary_paths_extras_versions_and_unprotected_archives_fail_before_unpack(self):
        self.guard.prepare("a" * 32, self.context)
        for payload in [b"/etc/private\n", b"/var/cache/apt/archives/../private.deb\n",
                        b"/var/cache/apt/archives/bash_5.2-2_amd64.deb\n" * 2, b"", b"VERSION 2\n"]:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(PolicyError, "package_guard_unsafe"):
                    self.guard.verify("a" * 32, payload)
        self.archives["/var/cache/apt/archives/bash_5.2-2_amd64.deb"] = ("bash", "5.2-3", "amd64")
        with self.assertRaisesRegex(PolicyError, "package_guard_unsafe"):
            self.guard.verify("a" * 32, b"/var/cache/apt/archives/bash_5.2-2_amd64.deb\n")
        artifact = Path(self.directory.name) / "unsafe.deb"
        artifact.write_bytes(b"not a real archive")
        artifact.chmod(0o666)
        with self.assertRaisesRegex(PolicyError, "package_guard_unsafe"):
            archive_metadata(str(artifact))


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now, self.calls, self.installed = 1000.0, [], False
        self.job_started, self.timer_active, self.package_busy = False, False, False
        self.apt_config = b'APT::Get::AllowUnauthenticated "false";\n'
        self.config = {"state_dir": self.directory.name, "targets": {"guest": {"kind": "lxc", "units": ["example.service"]}},
                       "maintenance_policies": {"guest": {
                           "reviewed_os_packages": ["bash", "libexample1"], "allowed_origins": ["Debian"],
                           "allowed_codenames": ["stable"], "denied_packages": [], "verification_units": ["example.service"],
                           "apt_configuration_digest": hashlib.sha256(self.apt_config).hexdigest(), "guard_digest": "e" * 64}}}
        self.engine = AptMaintenance(self.config, command=self.command, clock=lambda: self.now)
        self.addCleanup(self.engine.close)

    def command(self, target, argv, payload=b"", *, install=False):
        self.calls.append((target, argv, payload, install))
        if install:
            self.installed = True
            return b""
        if "identity" in argv:
            return json.dumps({"version": 1, "machine_id": "b" * 32, "boot_id": "boot-before", "guard_digest": "e" * 64}).encode()
        if "package-state" in argv:
            return json.dumps({"version": 1, "idle": not self.package_busy}).encode()
        if argv[:2] == ["/usr/bin/apt-config", "dump"]:
            return self.apt_config
        if "--simulate" in argv:
            return SIMULATION.encode()
        if "indextargets" in argv:
            return b"Identifier: Packages\nDescription: https://archive.example/debian stable/main amd64 Packages\nOrigin: Debian\nCodename: stable\nComponent: main\nArchitecture: amd64\nTrusted: yes\n"
        if argv[:2] == ["/usr/bin/apt-cache", "policy"]:
            name = argv[-1]
            old, new = ("5.2-1", "5.2-2") if name == "bash" else ("(none)", "1.0-1")
            return (f"{name}:\n  Installed: {old}\n  Candidate: {new}\n  Version table:\n     {new} 500\n        500 https://archive.example/debian stable/main amd64 Packages\n").encode()
        if "*.service" in argv:
            output = "Id=example.service\nActiveState=active\nType=simple\nTransient=no\nFragmentPath=/usr/lib/systemd/system/example.service\n\n"
            output += "Id=periodic.service\nActiveState=" + ("active" if self.timer_active else "inactive") + "\nType=oneshot\nTransient=no\nFragmentPath=/usr/lib/systemd/system/periodic.service\n\n"
            if self.job_started:
                output += "Id=codex-messaging-job-" + "a" * 32 + ".service\nActiveState=active\nType=exec\nTransient=yes\nFragmentPath=/run/systemd/transient/codex-messaging-job-" + "a" * 32 + ".service\n"
            return output.encode()
        if argv[0] == "/usr/bin/stat":
            return b"0:600:regular file\n"
        if argv[0] == "/usr/bin/dpkg-query":
            return b"bash\t5.2-2\tamd64\tinstalled\nlibexample1\t1.0-1\tamd64\tinstalled\n" if self.installed else b""
        return b""

    def test_attestation_is_exact_fresh_and_required_for_package_plan(self):
        with self.assertRaisesRegex(PolicyError, "recovery_attestation_missing"):
            self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")
        digest = self.engine.attest("guest", "b" * 32, "boot-before", "reviewed-1")
        context = self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")
        self.assertEqual(context["digest"], digest)
        self.assertEqual(context["packages"][0]["candidate"], "5.2-2")
        self.now += 601
        with self.assertRaisesRegex(PolicyError, "recovery_attestation_missing"):
            self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")

    def test_exact_plan_installs_once_with_guard_no_remove_and_no_reboot(self):
        self.engine.attest("guest", "b" * 32, "boot-before", "reviewed-1")
        context = self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")
        snapshot = Snapshot("guest", "lxc", "management", "node-a", "reviewed-1", context["digest"], True,
                            package_changes=tuple(PackageChange(**p) for p in context["packages"]), boot_id="boot-before")
        plan = Plan("guest", "lxc", "os_maintenance", (), snapshot)
        self.assertFalse(self.engine.verify(plan))
        self.engine.execute(plan, "a" * 32)
        self.package_busy = True
        self.assertFalse(self.engine.verify(plan))
        self.package_busy = False
        self.assertTrue(self.engine.verify(plan))
        installs = [call for call in self.calls if call[3]]
        self.assertEqual(len(installs), 1)
        self.assertIn("--no-remove", installs[0][1])
        self.assertIn("bash=5.2-2", installs[0][1])
        self.assertIn("libexample1=1.0-1", installs[0][1])
        self.assertTrue(any("Pre-Install-Pkgs" in value and "guard --job " + "a" * 32 in value for value in installs[0][1]))
        self.assertFalse(any(value in {"reboot", "autoremove", "dist-upgrade"} for call in self.calls for value in call[1]))
        with self.assertRaisesRegex(PolicyError, "recovery_attestation_missing"):
            self.engine.execute(plan, "b" * 32)
        self.assertEqual(len([call for call in self.calls if call[3]]), 1)

    def test_changed_service_inventory_after_refresh_requires_fresh_plan_without_install(self):
        self.engine.attest("guest", "b" * 32, "boot-before", "reviewed-1")
        context = self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")
        snapshot = Snapshot("guest", "lxc", "management", "node-a", "reviewed-1", context["digest"], True,
                            package_changes=tuple(PackageChange(**p) for p in context["packages"]), boot_id="boot-before")
        plan = Plan("guest", "lxc", "os_maintenance", (), snapshot)
        original = self.engine.command
        refreshed = []

        def changed(target, argv, payload=b"", *, install=False):
            if "update" in argv:
                refreshed.append(True)
            if refreshed and "*.service" in argv:
                return original(target, argv, payload, install=install) + b"\nId=new.service\nActiveState=active\nType=simple\nTransient=no\nFragmentPath=/usr/lib/systemd/system/new.service\n"
            return original(target, argv, payload, install=install)

        self.engine.command = changed
        with self.assertRaisesRegex(PolicyError, "plan_changed"):
            self.engine.execute(plan, "a" * 32)
        self.assertFalse(any(call[3] for call in self.calls))

    def test_periodic_oneshots_and_our_root_owned_job_do_not_change_the_approved_impact(self):
        digest = self.engine.attest("guest", "b" * 32, "boot-before", "reviewed-1")
        self.timer_active, self.job_started = True, True
        context = self.engine.preview("guest", "b" * 32, "boot-before", "reviewed-1")
        self.assertEqual(context["digest"], digest)
        self.assertEqual(context["active_units"], ["example.service"])

    def test_package_process_has_closed_input_and_no_killer_timeout(self):
        class FakePackage:
            def wait(self):
                return 0

        with patch("codex_messaging.maintenance.subprocess.Popen", return_value=FakePackage()) as boundary:
            self.assertEqual(run_package(["/fixed/fake-apt"]), b"")
        arguments = boundary.call_args.kwargs
        self.assertNotIn("timeout", arguments)
        self.assertEqual(arguments["stdin"], subprocess.DEVNULL)
        self.assertEqual(arguments["env"]["DEBIAN_FRONTEND"], "noninteractive")
        self.assertEqual(arguments["env"]["LC_ALL"], "C")


if __name__ == "__main__":
    unittest.main()
