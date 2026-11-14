"""Exercise broker policy and recovery through its public API with fake targets."""

import dataclasses
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.operations import (
    OperationsBroker, PackageChange, PolicyError, RemoteResult, Snapshot,
    Target, TargetRegistry,
)


class Remote:
    def __init__(self):
        self.dispatched = []
        self.results = {}
        self.override = {}
        self.lose_reply = False
        self.before_dispatch = None

    def inspect(self, target, operation, parameters):
        values = dict(
            target_id=target.target_id, target_kind=target.kind,
            management_target_id="management", management_host_id="node-a",
            runbook_version="reviewed-1", plan_version="transaction-1",
            preflight_verified=True, impact=("Registered service interruption",),
            verification=("Required application health",), boot_id="old-boot",
            preconditions=("identity", "ownership", "dependency_impact", "application_health",
                           "independent_access", "recovery_ready", "quorum", "replication",
                           "backups", "resolver_failover", "affected_guests", "package_transaction",
                           "service_impact", "no_prompts", "no_automatic_reboot"),
        )
        if operation == "os_maintenance":
            values["package_changes"] = (PackageChange("example", "1", "2"),)
        values.update(self.override)
        return Snapshot(**values)

    def dispatch(self, job_id, plan):
        if self.before_dispatch:
            self.before_dispatch(job_id, plan)
        self.dispatched.append((job_id, plan))
        result = self.results.setdefault(job_id, RemoteResult("running"))
        if self.lose_reply:
            raise ConnectionError("credential-bearing remote error")
        return result

    def query(self, job_id):
        return self.results.get(job_id, RemoteResult("unknown"))


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "operations.sqlite"
        self.now = 1000.0
        self.remote = Remote()
        self.registry = TargetRegistry([
            Target("management", "vm", aliases=("gateway",)),
            Target("node-a", "host", aliases=("current-host",)),
            Target("node-b", "host"),
            Target("guest", "vm", aliases=("application",), units=("example.service",)),
            Target("container", "lxc"),
        ])
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        self.addCleanup(lambda: self.broker.close())

    def prepare(self, operation="service_restart", target="application", **parameters):
        if operation == "service_restart" and not parameters:
            parameters = {"unit": "example.service"}
        return self.broker.prepare(1, 2, target, operation, parameters)

    def approve(self, prepared):
        return self.broker.approve(1, 2, prepared.approval_id, prepared.plan_digest)

    def test_approval_is_immutable_and_replay_does_not_dispatch(self):
        prepared = self.prepare()
        self.assertEqual(prepared.plan.target_id, "guest")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            prepared.plan.target_id = "management"
        job = self.approve(prepared)
        self.assertEqual(job.state, "running")
        self.assertEqual(self.broker.status(job.job_id), job)
        with self.assertRaisesRegex(PolicyError, "approval_used"):
            self.approve(prepared)
        self.assertEqual([item[0] for item in self.remote.dispatched], [job.job_id])

    def test_registry_schema_and_live_identity_reject_unsafe_operations(self):
        cases = [
            ("gateway", "guest_reboot", {}, {}, "management_protected"),
            ("management", "os_maintenance", {}, {}, "management_protected"),
            ("current-host", "host_reboot", {}, {}, "management_protected"),
            ("node-b", "host_reboot", {}, {"management_host_id": ""}, "identity_unknown"),
            ("node-b", "host_reboot", {}, {"management_host_id": "node-b"}, "management_protected"),
            ("guest", "service_restart", {"unit": "unknown.service"}, {}, "parameters_invalid"),
            ("guest", "service_restart", {"unit": "example.service", "shell": "secret"}, {}, "parameters_invalid"),
            ("guest", "shell", {}, {}, "operation_unsupported"),
            ("guest", "host_reboot", {}, {}, "operation_unsupported"),
            ("guest", "guest_reboot", {}, {"target_id": "management"}, "identity_changed"),
            ("guest", "guest_reboot", {}, {"affected_target_ids": ("gateway",)}, "identity_unknown"),
            ("guest", "guest_reboot", {}, {"affected_target_ids": ("management",)}, "management_protected"),
            ("node-b", "host_reboot", {}, {"affected_target_ids": ("node-a",)}, "management_protected"),
            ("guest", "guest_reboot", {}, {"preflight_verified": False}, "preflight_failed"),
            ("guest", "os_maintenance", {}, {"package_changes": (PackageChange("example", "1", "", "remove"),)}, "package_plan_unsafe"),
        ]
        for target, operation, parameters, override, code in cases:
            with self.subTest(target=target, operation=operation, code=code):
                self.remote.override = override
                with self.assertRaises(PolicyError) as error:
                    self.broker.prepare(1, 2, target, operation, parameters)
                self.assertEqual(error.exception.code, code)
        self.assertEqual(self.remote.dispatched, [])

    def test_approval_binds_identity_expiry_and_revalidated_package_plan(self):
        prepared = self.prepare("os_maintenance")
        for user, chat, digest in [(9, 2, prepared.plan_digest), (1, 9, prepared.plan_digest), (1, 2, "changed")]:
            with self.subTest(user=user, chat=chat, digest=digest):
                with self.assertRaisesRegex(PolicyError, "approval_mismatch"):
                    self.broker.approve(user, chat, prepared.approval_id, digest)
        self.now += 600
        with self.assertRaisesRegex(PolicyError, "approval_expired"):
            self.approve(prepared)
        prepared = self.prepare("os_maintenance")
        self.remote.override = {"package_changes": (PackageChange("example", "1", "3"),)}
        with self.assertRaisesRegex(PolicyError, "plan_changed"):
            self.approve(prepared)
        self.remote.override = {}
        with self.assertRaisesRegex(PolicyError, "approval_used"):
            self.approve(prepared)
        self.assertEqual(self.remote.dispatched, [])

    def test_malformed_ids_and_package_payloads_have_safe_error_codes(self):
        for method, arguments in [
            (self.broker.status, ({"private": "payload"},)),
            (self.broker.approve, (1, 2, ["private payload"], "digest")),
        ]:
            with self.subTest(method=method.__name__):
                with self.assertRaises(PolicyError) as error:
                    method(*arguments)
                self.assertEqual(str(error.exception), "request_invalid")
        self.remote.override = {"package_changes": (PackageChange("example", "1", ["private payload"]),)}
        with self.assertRaisesRegex(PolicyError, "package_plan_unsafe"):
            self.prepare("os_maintenance")

    def test_lost_dispatch_reply_and_restart_reconcile_the_original_job(self):
        prepared = self.prepare("os_maintenance")
        pending = self.prepare("guest_reboot")
        self.remote.before_dispatch = lambda job_id, plan: self.assertEqual(
            self.broker.status(job_id).state, "dispatching")
        self.remote.lose_reply = True
        job = self.approve(prepared)
        self.assertEqual((job.state, job.error_code), ("uncertain", "remote_uncertain"))
        self.broker.close()
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        with self.assertRaisesRegex(PolicyError, "approval_used"):
            self.approve(pending)
        self.assertEqual(self.broker.status(job.job_id).state, "uncertain")
        with self.assertRaisesRegex(PolicyError, "reconciliation_required"):
            self.broker.resume()
        self.remote.results[job.job_id] = RemoteResult("verified", healthy=True)
        recovered = self.broker.reconcile(job.job_id)
        self.assertEqual(recovered.state, "awaiting_documentation")
        self.assertEqual([item[0] for item in self.remote.dispatched], [job.job_id])

    def test_pause_stop_and_global_lock_preserve_an_active_package_step(self):
        active = self.approve(self.prepare("os_maintenance"))
        pending = self.prepare("guest_reboot")
        with self.assertRaisesRegex(PolicyError, "change_busy"):
            self.approve(pending)
        self.broker.pause()
        with self.assertRaisesRegex(PolicyError, "changes_paused"):
            self.approve(pending)
        diagnostic = self.broker.diagnose(1, 2, "gateway", {"probe": "health"})
        self.assertEqual(diagnostic.operation, "diagnose")
        self.broker.stop()
        self.assertEqual(self.broker.status(active.job_id).state, "running")
        self.broker.resume()
        with self.assertRaisesRegex(PolicyError, "approval_used"):
            self.approve(pending)
        self.assertEqual([plan.operation for _, plan in self.remote.dispatched], ["os_maintenance", "diagnose"])

    def test_verified_reboot_and_publication_progress_cannot_repeat_maintenance(self):
        job = self.approve(self.prepare("guest_reboot"))
        self.remote.results[job.job_id] = RemoteResult("verified", healthy=True, boot_id="old-boot")
        self.assertEqual(self.broker.reconcile(job.job_id).error_code, "recovery_unverified")
        self.remote.results[job.job_id] = RemoteResult("verified", healthy=True, boot_id="new-boot")
        self.assertEqual(self.broker.reconcile(job.job_id).state, "awaiting_documentation")
        with self.assertRaisesRegex(PolicyError, "publication_transition"):
            self.broker.publication(job.job_id, "completed")
        self.assertEqual(self.broker.publication(job.job_id, "awaiting_sync").state, "awaiting_sync")
        self.remote.results[job.job_id] = RemoteResult("unknown")
        self.assertEqual(self.broker.reconcile(job.job_id).state, "awaiting_sync")
        self.broker.close()
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        self.assertEqual(self.broker.status(job.job_id).state, "awaiting_sync")
        self.assertEqual(self.broker.publication(job.job_id, "completed").state, "completed")
        self.assertEqual([item[0] for item in self.remote.dispatched], [job.job_id])

    def test_missing_proofs_mutable_snapshots_and_malformed_requests_fail_closed(self):
        cases = [
            ({"preconditions": ()}, "preflight_failed"),
            ({"impact": ["mutable impact"]}, "snapshot_invalid"),
            ({"preconditions": ("identity", "unreviewed proof")}, "snapshot_invalid"),
            ({"boot_id": None}, "preflight_failed"),
            ({"management_host_id": ["private payload"]}, "identity_unknown"),
        ]
        for override, code in cases:
            with self.subTest(override=override):
                self.remote.override = override
                with self.assertRaises(PolicyError) as error:
                    self.prepare("host_reboot", "node-b")
                self.assertEqual(str(error.exception), code)
        self.remote.override = {}
        for parameters in ({"probe": ["private payload"]}, {"probe": 4}, ["payload"]):
            with self.subTest(parameters=parameters):
                with self.assertRaises(PolicyError) as error:
                    self.broker.diagnose(1, 2, "guest", parameters)
                self.assertEqual(str(error.exception), "parameters_invalid")
        for user_id, chat_id in [(True, 2), (1, -2), ("private payload", 2)]:
            with self.subTest(user_id=user_id, chat_id=chat_id):
                with self.assertRaisesRegex(PolicyError, "identity_invalid"):
                    self.broker.prepare(user_id, chat_id, "guest", "guest_reboot")
        self.assertEqual(self.remote.dispatched, [])

    def test_crash_before_remote_dispatch_never_submits_a_replacement_job(self):
        prepared = self.prepare("os_maintenance")
        journalled = []

        def crash(job_id, plan):
            journalled.append(job_id)
            raise SystemExit("simulated process crash")

        self.remote.before_dispatch = crash
        with self.assertRaises(SystemExit):
            self.approve(prepared)
        job_id = journalled[0]
        self.assertEqual(self.broker.status(job_id).state, "dispatching")
        self.broker.close()
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        self.assertEqual(self.broker.status(job_id).state, "uncertain")
        self.assertEqual(self.broker.reconcile(job_id).state, "uncertain")
        with self.assertRaisesRegex(PolicyError, "approval_used"):
            self.approve(prepared)
        self.assertEqual(self.remote.dispatched, [])

    def test_journal_and_wal_are_private(self):
        self.prepare()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(str(self.path) + "-wal").stat().st_mode & 0o777, 0o600)

    def test_management_migration_after_approval_denies_reboot(self):
        prepared = self.prepare("host_reboot", "node-b")
        self.remote.override = {"management_host_id": "node-b"}
        with self.assertRaisesRegex(PolicyError, "management_protected"):
            self.approve(prepared)
        self.assertEqual(self.remote.dispatched, [])

    def test_untyped_remote_snapshot_and_boot_proof_cannot_authorize_success(self):
        for override in [
            {"runbook_version": ["mutable"]}, {"plan_version": {"mutable": True}},
            {"package_changes": (PackageChange("example", ["mutable"], "2"),)},
        ]:
            with self.subTest(override=override):
                self.remote.override = override
                with self.assertRaisesRegex(PolicyError, "snapshot_invalid"):
                    self.prepare()
        self.remote.override = {}
        job = self.approve(self.prepare("guest_reboot"))
        self.remote.results[job.job_id] = RemoteResult("verified", healthy=True, boot_id=["mutable"])
        self.assertEqual(self.broker.reconcile(job.job_id).state, "uncertain")

    def test_concurrent_approval_delivery_cannot_create_two_remote_jobs(self):
        prepared = self.prepare("os_maintenance")
        start = threading.Barrier(2)

        def submit():
            start.wait(timeout=5)
            try:
                return self.approve(prepared).state
            except PolicyError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: submit(), range(2)))
        self.assertCountEqual(outcomes, ["running", "approval_used"])
        self.assertEqual(len(self.remote.dispatched), 1)

    def test_committed_jobs_are_discoverable_after_losing_the_broker_reply(self):
        job = self.approve(self.prepare())
        self.broker.close()
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        outstanding = self.broker.recoverable_jobs()
        self.assertEqual([item.job_id for item in outstanding], [job.job_id])
        self.assertEqual(outstanding[0].state, "uncertain")
        self.assertEqual(len(self.remote.dispatched), 1)

    def test_diagnostics_are_bounded_persisted_and_separate_from_status_metadata(self):
        job = self.broker.diagnose(1, 2, "guest")
        self.remote.results[job.job_id] = RemoteResult("verified", healthy=True,
                                                       diagnostics=(("service_state", "inactive"),))
        self.assertEqual(self.broker.reconcile(job.job_id).state, "completed")
        self.assertEqual(self.broker.diagnostic_result(job.job_id), (("service_state", "inactive"),))
        self.broker.close()
        self.broker = OperationsBroker(self.path, self.registry, self.remote, clock=lambda: self.now)
        self.assertEqual(self.broker.diagnostic_result(job.job_id), (("service_state", "inactive"),))
        other = self.broker.diagnose(1, 2, "guest")
        self.remote.results[other.job_id] = RemoteResult("verified", healthy=True, diagnostics=(("raw", "x" * 65537),))
        self.assertEqual(self.broker.reconcile(other.job_id).state, "uncertain")
        self.assertEqual(self.broker.diagnostic_result(other.job_id), ())

    def test_lxc_reboot_plan_requires_a_typed_parent_boot_proof(self):
        with self.assertRaisesRegex(PolicyError, "preflight_failed"):
            self.prepare("guest_reboot", "container")
        self.remote.override = {"parent_boot_id": ["mutable"]}
        with self.assertRaisesRegex(PolicyError, "snapshot_invalid"):
            self.prepare("guest_reboot", "container")
        self.remote.override = {"parent_boot_id": "parent-before"}
        prepared = self.prepare("guest_reboot", "container")
        self.assertEqual(prepared.plan.snapshot.parent_boot_id, "parent-before")
        self.assertEqual(self.remote.dispatched, [])


if __name__ == "__main__":
    unittest.main()
