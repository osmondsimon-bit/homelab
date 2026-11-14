"""Broker typed operations, immutable approvals and durable remote-job recovery."""

from dataclasses import asdict, dataclass
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time
from typing import Mapping, Protocol


OPERATIONS = frozenset({"diagnose", "service_restart", "guest_reboot", "host_reboot", "os_maintenance"})
KINDS = {
    "host": OPERATIONS - {"guest_reboot"},
    "vm": OPERATIONS - {"host_reboot"},
    "lxc": OPERATIONS - {"host_reboot"},
    "appliance": frozenset({"diagnose", "guest_reboot"}),
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
UNIT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,126}\.service\Z")
PROOFS = {
    "diagnose": frozenset(),
    "service_restart": frozenset({"identity", "dependency_impact", "application_health"}),
    "guest_reboot": frozenset({"identity", "ownership", "independent_access", "recovery_ready"}),
    "host_reboot": frozenset({"identity", "ownership", "quorum", "replication", "backups",
                              "resolver_failover", "independent_access", "recovery_ready", "affected_guests"}),
    "os_maintenance": frozenset({"identity", "ownership", "package_transaction", "service_impact",
                                 "recovery_ready", "no_prompts", "no_automatic_reboot"}),
}


class PolicyError(Exception):
    """Expose only a stable safe error code to callers."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _safe(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except PolicyError:
            raise
        except (TypeError, ValueError, AttributeError):
            raise PolicyError("request_invalid") from None
        except (sqlite3.Error, OSError):
            raise PolicyError("journal_unavailable") from None
        except Exception:
            raise PolicyError("broker_unavailable") from None
    return call


@dataclass(frozen=True)
class Target:
    target_id: str
    kind: str
    aliases: tuple[str, ...] = ()
    units: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()


class TargetRegistry:
    @_safe
    def __init__(self, targets):
        self._targets = {}
        for target in targets:
            if (not isinstance(target, Target) or target.kind not in KINDS
                    or any(not isinstance(values, tuple) for values in
                           (target.aliases, target.units, target.operations))
                    or any(not isinstance(unit, str) or not UNIT.fullmatch(unit) for unit in target.units)
                    or not set(target.operations) <= KINDS[target.kind]):
                raise PolicyError("registry_invalid")
            for name in (target.target_id, *target.aliases):
                if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in self._targets:
                    raise PolicyError("registry_invalid")
                self._targets[name] = target

    @_safe
    def resolve(self, alias):
        try:
            return self._targets[alias]
        except (KeyError, TypeError):
            raise PolicyError("target_unknown") from None


@dataclass(frozen=True)
class PackageChange:
    name: str
    current: str
    candidate: str
    action: str = "upgrade"


@dataclass(frozen=True)
class Snapshot:
    target_id: str
    target_kind: str
    management_target_id: str
    management_host_id: str
    runbook_version: str
    plan_version: str
    preflight_verified: bool
    affected_target_ids: tuple[str, ...] = ()
    package_changes: tuple[PackageChange, ...] = ()
    impact: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    boot_id: str | None = None
    reboot_required: bool = False
    parent_boot_id: str | None = None


@dataclass(frozen=True)
class Plan:
    target_id: str
    target_kind: str
    operation: str
    parameters: tuple[tuple[str, str], ...]
    snapshot: Snapshot


@dataclass(frozen=True)
class Prepared:
    approval_id: str
    plan_digest: str
    plan: Plan
    expires_at: float


@dataclass(frozen=True)
class Job:
    job_id: str
    state: str
    error_code: str | None
    plan_digest: str
    target_id: str
    operation: str


@dataclass(frozen=True)
class RemoteResult:
    state: str
    healthy: bool = False
    boot_id: str | None = None
    diagnostics: tuple[tuple[str, str], ...] = ()


def bounded_diagnostics(values):
    """Allow at most sixteen text fields and 64 KiB of selected model context."""
    if (not isinstance(values, tuple) or len(values) > 16
            or any(not isinstance(item, tuple) or len(item) != 2
                   or not isinstance(item[0], str) or not IDENTIFIER.fullmatch(item[0])
                   or not isinstance(item[1], str) or len(item[1].encode()) > 65536 for item in values)
            or len({item[0] for item in values}) != len(values)
            or sum(len(key.encode()) + len(value.encode()) for key, value in values) > 65536):
        raise PolicyError("diagnostics_invalid")
    return values


class RemoteAdapter(Protocol):
    """Trusted boundary: inspect is read-only; dispatch runs one reviewed action.

    Dispatchers must journal the original job ID and plan digest before effects,
    reject differing reuse, recheck live guards before the action, and supervise
    it across disconnects. They report verified only after actual health/recovery
    checks. Neither a command acknowledgement nor an SSH exit is verification.
    Query must never submit work. This protocol cannot promise exactly-once effects.
    """

    def inspect(self, target: Target, operation: str, parameters: Mapping[str, str]) -> Snapshot: ...
    def dispatch(self, job_id: str, plan: Plan) -> RemoteResult: ...
    def query(self, job_id: str) -> RemoteResult: ...


def _encoded(plan):
    return json.dumps(asdict(plan), sort_keys=True, separators=(",", ":"))


def _digest(plan):
    return hashlib.sha256(_encoded(plan).encode()).hexdigest()


def _decoded(value):
    data = json.loads(value)
    snapshot = data.pop("snapshot")
    snapshot["package_changes"] = tuple(PackageChange(**p) for p in snapshot["package_changes"])
    for key in ("affected_target_ids", "impact", "verification", "preconditions"):
        snapshot[key] = tuple(snapshot[key])
    return Plan(**data | {"parameters": tuple(tuple(p) for p in data["parameters"]),
                          "snapshot": Snapshot(**snapshot)})


def plan_to_wire(plan):
    """Return an independent JSON-compatible copy of an immutable plan."""
    return json.loads(_encoded(plan))


@_safe
def snapshot_from_wire(value):
    """Decode a closed-schema snapshot; broker/dispatcher policy validates facts."""
    from dataclasses import fields
    if not isinstance(value, dict) or set(value) != {field.name for field in fields(Snapshot)}:
        raise PolicyError("wire_invalid")
    data = dict(value)
    for key in ("affected_target_ids", "package_changes", "impact", "verification", "preconditions"):
        if not isinstance(data[key], list):
            raise PolicyError("wire_invalid")
        data[key] = tuple(data[key])
    names = {field.name for field in fields(PackageChange)}
    if any(not isinstance(p, dict) or set(p) != names for p in data["package_changes"]):
        raise PolicyError("wire_invalid")
    data["package_changes"] = tuple(PackageChange(**p) for p in data["package_changes"])
    return Snapshot(**data)


@_safe
def plan_from_wire(value):
    """Decode a closed-schema plan without granting it execution authority."""
    if (not isinstance(value, dict)
            or set(value) != {"target_id", "target_kind", "operation", "parameters", "snapshot"}
            or not isinstance(value["parameters"], list)
            or any(not isinstance(p, list) or len(p) != 2
                   or any(not isinstance(item, str) for item in p) for p in value["parameters"])):
        raise PolicyError("wire_invalid")
    return Plan(value["target_id"], value["target_kind"], value["operation"],
                tuple(tuple(p) for p in value["parameters"]), snapshot_from_wire(value["snapshot"]))


def plan_digest(plan):
    """Hash the complete normalized plan for broker and remote journal agreement."""
    return _digest(plan)


class OperationsBroker:
    """One broker owns a journal; injected remote adapters carry all remote authority."""

    @_safe
    def __init__(self, db_path, registry, remote, *, clock=time.time):
        self.registry, self.remote, self.clock = registry, remote, clock
        self._lock = threading.RLock()
        path = Path(db_path)
        parent = path.parent.stat()
        if str(db_path) == ":memory:" or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
            raise PolicyError("journal_permissions")
        for suffix in ("", "-wal", "-shm"):
            journal_path = str(path) + suffix
            if suffix and not os.path.lexists(journal_path):
                continue
            descriptor = os.open(journal_path, os.O_RDWR | os.O_NOFOLLOW | (0 if suffix else os.O_CREAT), 0o600)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise PolicyError("journal_permissions")
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
        self._db = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        restarting = self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='control' AND type='table'").fetchone() is not None
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY, paused INTEGER);
            INSERT OR IGNORE INTO control VALUES (1, 0);
            CREATE TABLE IF NOT EXISTS approvals (
              id TEXT PRIMARY KEY, user_id INTEGER, chat_id INTEGER, expires REAL,
              digest TEXT, plan TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, state TEXT, error TEXT, digest TEXT, plan TEXT,
              is_change INTEGER);
        """)
        if "diagnostics" not in {row[1] for row in self._db.execute("PRAGMA table_info(jobs)")}:
            self._db.execute("ALTER TABLE jobs ADD COLUMN diagnostics TEXT NOT NULL DEFAULT '[]'")
        if restarting:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute("UPDATE control SET paused=1")
            self._db.execute("UPDATE approvals SET state='invalidated' WHERE state='pending'")
            self._db.execute("UPDATE jobs SET state='uncertain', error='recovery_required' "
                             "WHERE state IN ('dispatching', 'running')")
            self._db.execute("COMMIT")

    @_safe
    def close(self):
        with self._lock:
            self._db.close()

    def _plan(self, target_alias, operation, parameters):
        target = self.registry.resolve(target_alias)
        allowed = target.operations or KINDS[target.kind]
        if not isinstance(operation, str) or operation not in allowed:
            raise PolicyError("operation_unsupported")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in parameters.items()):
            raise PolicyError("parameters_invalid")
        valid = not parameters
        if operation == "service_restart":
            valid = set(parameters) == {"unit"} and parameters["unit"] in target.units
        elif operation == "diagnose" and parameters:
            probe = parameters.get("probe")
            valid = (set(parameters) == {"probe"} and probe in
                     {"health", "resources", "packages", "reboot", "dns"})
            if probe == "unit_logs":
                valid = set(parameters) == {"probe", "unit"} and parameters["unit"] in target.units
        if not valid:
            raise PolicyError("parameters_invalid")
        try:
            snapshot = self.remote.inspect(target, operation, parameters)
        except Exception:
            raise PolicyError("inspection_unavailable") from None
        self._validate_snapshot(target, operation, snapshot)
        return Plan(target.target_id, target.kind, operation, tuple(sorted(parameters.items())), snapshot)

    def _validate_snapshot(self, target, operation, snapshot):
        if not isinstance(snapshot, Snapshot):
            raise PolicyError("identity_unknown")
        if (snapshot.target_id, snapshot.target_kind) != (target.target_id, target.kind):
            raise PolicyError("identity_changed")
        try:
            management = self.registry.resolve(snapshot.management_target_id)
            host = self.registry.resolve(snapshot.management_host_id)
            affected = tuple(self.registry.resolve(item) for item in snapshot.affected_target_ids)
            canonical = (management.target_id == snapshot.management_target_id
                         and host.target_id == snapshot.management_host_id
                         and all(t.target_id == name for t, name in zip(affected, snapshot.affected_target_ids)))
        except (PolicyError, TypeError):
            raise PolicyError("identity_unknown") from None
        if not canonical or management.kind != "vm" or host.kind != "host":
            raise PolicyError("identity_unknown")
        sequences = (snapshot.affected_target_ids, snapshot.impact, snapshot.verification, snapshot.preconditions)
        if (any(not isinstance(values, tuple) or len(values) > 128
                or any(not isinstance(v, str) or not v or len(v) > 240 or not v.isprintable() for v in values)
                for values in sequences)
                or not isinstance(snapshot.package_changes, tuple)
                or len(snapshot.package_changes) > 4096
                or operation != "os_maintenance" and snapshot.package_changes
                or any(not isinstance(v, str) or not IDENTIFIER.fullmatch(v)
                       for v in (snapshot.runbook_version, snapshot.plan_version))
                or snapshot.boot_id is not None and
                   (not isinstance(snapshot.boot_id, str) or not IDENTIFIER.fullmatch(snapshot.boot_id))
                or snapshot.parent_boot_id is not None and
                   (not isinstance(snapshot.parent_boot_id, str) or not IDENTIFIER.fullmatch(snapshot.parent_boot_id))
                or type(snapshot.preflight_verified) is not bool
                or type(snapshot.reboot_required) is not bool
                or not set(snapshot.preconditions) <= frozenset().union(*PROOFS.values())):
            raise PolicyError("snapshot_invalid")
        if operation != "diagnose":
            if (target.target_id == management.target_id
                    or management.target_id in snapshot.affected_target_ids
                    or operation.endswith("reboot") and host.target_id in
                    (target.target_id, *snapshot.affected_target_ids)):
                raise PolicyError("management_protected")
            if (snapshot.preflight_verified is not True or not snapshot.runbook_version
                    or not snapshot.plan_version or not snapshot.impact or not snapshot.verification
                    or not PROOFS[operation] <= set(snapshot.preconditions)):
                raise PolicyError("preflight_failed")
            if operation.endswith("reboot") and not snapshot.boot_id:
                raise PolicyError("preflight_failed")
            if operation == "guest_reboot" and target.kind == "lxc" and not snapshot.parent_boot_id:
                raise PolicyError("preflight_failed")
            if operation == "os_maintenance" and any(
                not isinstance(p, PackageChange) or p.action not in {"upgrade", "install"}
                or not isinstance(p.name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9+.:-]{0,127}", p.name)
                or not isinstance(p.current, str) or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{0,128}", p.current)
                or not isinstance(p.candidate, str) or not re.fullmatch(r"[A-Za-z0-9.+:~_-]{1,128}", p.candidate)
                for p in snapshot.package_changes
            ):
                raise PolicyError("package_plan_unsafe")

    @_safe
    def prepare(self, user_id, chat_id, target_alias, operation, parameters=None):
        self._identity(user_id, chat_id)
        if parameters is not None and not isinstance(parameters, dict):
            raise PolicyError("parameters_invalid")
        plan = self._plan(target_alias, operation, dict(parameters or {}))
        result = Prepared(secrets.token_urlsafe(24), _digest(plan), plan, self.clock() + 600)
        with self._lock:
            self._db.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                             (result.approval_id, user_id, chat_id, result.expires_at,
                              result.plan_digest, _encoded(plan)))
        return result

    @_safe
    def approve(self, user_id, chat_id, approval_id, plan_digest):
        self._identity(user_id, chat_id)
        self._opaque(approval_id)
        self._opaque(plan_digest)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
                if row is None:
                    raise PolicyError("approval_unknown")
                if row["state"] != "pending":
                    raise PolicyError("approval_used")
                if (row["user_id"], row["chat_id"], row["digest"]) != (user_id, chat_id, plan_digest):
                    raise PolicyError("approval_mismatch")
                if self.clock() >= row["expires"]:
                    raise PolicyError("approval_expired")
                plan = _decoded(row["plan"])
                if plan.operation != "diagnose":
                    self._change_allowed()
                try:
                    current = self._plan(plan.target_id, plan.operation, dict(plan.parameters))
                    if _digest(current) != row["digest"]:
                        raise PolicyError("plan_changed")
                except PolicyError:
                    self._db.execute("UPDATE approvals SET state='invalidated' WHERE id=?", (approval_id,))
                    self._db.execute("COMMIT")
                    raise
                job_id = secrets.token_hex(16)
                self._db.execute("UPDATE approvals SET state='used' WHERE id=?", (approval_id,))
                self._db.execute("INSERT INTO jobs (id,state,error,digest,plan,is_change) VALUES (?, 'dispatching', NULL, ?, ?, ?)",
                                 (job_id, row["digest"], row["plan"], plan.operation != "diagnose"))
                self._db.execute("COMMIT")
            except BaseException:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise
        return self._dispatch(job_id, plan)

    def _change_allowed(self):
        if self._db.execute("SELECT paused FROM control").fetchone()[0]:
            raise PolicyError("changes_paused")
        if self._db.execute("SELECT 1 FROM jobs WHERE is_change=1 "
                            "AND state NOT IN ('completed', 'failed')").fetchone():
            raise PolicyError("change_busy")

    @_safe
    def diagnose(self, user_id, chat_id, target_alias, parameters=None):
        self._identity(user_id, chat_id)
        if parameters is not None and not isinstance(parameters, dict):
            raise PolicyError("parameters_invalid")
        plan = self._plan(target_alias, "diagnose", dict(parameters or {}))
        job_id = secrets.token_hex(16)
        with self._lock:
            self._db.execute("INSERT INTO jobs (id,state,error,digest,plan,is_change) VALUES (?, 'dispatching', NULL, ?, ?, 0)",
                             (job_id, _digest(plan), _encoded(plan)))
        return self._dispatch(job_id, plan)

    @staticmethod
    def _identity(user_id, chat_id):
        if type(user_id) is not int or type(chat_id) is not int or user_id <= 0 or chat_id <= 0:
            raise PolicyError("identity_invalid")

    @staticmethod
    def _opaque(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise PolicyError("request_invalid")

    def _dispatch(self, job_id, plan):
        try:
            result = self.remote.dispatch(job_id, plan)
        except Exception:
            result = RemoteResult("unknown")
        return self._result(job_id, plan, result)

    def _result(self, job_id, plan, result):
        state, error = "uncertain", "remote_uncertain"
        diagnostics = ()
        try:
            if isinstance(result, RemoteResult):
                diagnostics = bounded_diagnostics(result.diagnostics)
                if diagnostics and plan.operation != "diagnose":
                    raise PolicyError("diagnostics_invalid")
        except PolicyError:
            result = None
        if isinstance(result, RemoteResult):
            if result.state == "running":
                state, error = "running", None
            elif result.state == "failed":
                state, error = "failed", "remote_failed"
            elif result.state == "verified" and result.healthy is True:
                reboot_verified = (not plan.operation.endswith("reboot")
                                   or isinstance(result.boot_id, str) and IDENTIFIER.fullmatch(result.boot_id)
                                   and result.boot_id != plan.snapshot.boot_id)
                if reboot_verified:
                    state, error = ("completed" if plan.operation == "diagnose" else "awaiting_documentation"), None
                else:
                    error = "recovery_unverified"
        with self._lock:
            changed = self._db.execute("UPDATE jobs SET state=?, error=?, diagnostics=? WHERE id=? "
                                       "AND state IN ('dispatching', 'running', 'uncertain')",
                                       (state, error, json.dumps(diagnostics), job_id)).rowcount
            if changed and state in {"uncertain", "failed"}:
                self._db.execute("UPDATE control SET paused=1")
        return self.status(job_id)

    @_safe
    def reconcile(self, job_id):
        self._opaque(job_id)
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise PolicyError("job_unknown")
            if row["state"] not in {"dispatching", "running", "uncertain"}:
                return self.status(job_id)
            plan = _decoded(row["plan"])
        try:
            result = self.remote.query(job_id)
        except Exception:
            result = RemoteResult("unknown")
        return self._result(job_id, plan, result)

    @_safe
    def resume(self):
        with self._lock:
            if self._db.execute("SELECT 1 FROM jobs WHERE state='uncertain'").fetchone():
                raise PolicyError("reconciliation_required")
            self._db.execute("UPDATE control SET paused=0")

    @_safe
    def pause(self):
        with self._lock:
            self._db.execute("UPDATE control SET paused=1")

    @_safe
    def stop(self):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute("UPDATE control SET paused=1")
            self._db.execute("UPDATE approvals SET state='invalidated' WHERE state='pending'")
            self._db.execute("COMMIT")

    @_safe
    def publication(self, job_id, state):
        """Record a trusted publisher outcome without re-entering remote execution."""
        allowed = {"awaiting_documentation": {"awaiting_documentation", "awaiting_sync"},
                   "awaiting_sync": {"awaiting_sync", "completed"}, "completed": {"completed"}}
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                current = self.status(job_id)
                if state not in allowed.get(current.state, set()):
                    raise PolicyError("publication_transition")
                self._db.execute("UPDATE jobs SET state=?, error=NULL WHERE id=?", (state, job_id))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
        return self.status(job_id)

    @_safe
    def status(self, job_id):
        self._opaque(job_id)
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise PolicyError("job_unknown")
            plan = _decoded(row["plan"])
            return Job(row["id"], row["state"], row["error"], row["digest"],
                       plan.target_id, plan.operation)

    @_safe
    def recoverable_jobs(self):
        """Return safe outstanding metadata for the single enrolled coordinator."""
        with self._lock:
            rows = self._db.execute("SELECT id FROM jobs WHERE state NOT IN ('completed', 'failed') ORDER BY rowid").fetchall()
            return tuple(self.status(row["id"]) for row in rows)

    @_safe
    def diagnostic_result(self, job_id):
        """Read selected context for the worker; never include it in status/chat UI."""
        if self.status(job_id).operation != "diagnose":
            raise PolicyError("diagnostics_unavailable")
        with self._lock:
            row = self._db.execute("SELECT diagnostics FROM jobs WHERE id=?", (job_id,)).fetchone()
            return bounded_diagnostics(tuple(tuple(pair) for pair in json.loads(row[0])))
