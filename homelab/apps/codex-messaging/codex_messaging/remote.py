"""Carry closed typed requests over pinned SSH and retain original job routing."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import selectors
import signal
import sqlite3
import stat
import subprocess
import threading
import time

from .operations import PolicyError, RemoteResult, bounded_diagnostics, plan_digest, plan_to_wire, snapshot_from_wire

MAX_WIRE = 1024 * 1024
SAFE_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "HOME": "/nonexistent"}
SAFE_REMOTE_ERRORS = frozenset({
    "request_invalid", "target_unknown", "operation_unsupported", "parameters_invalid",
    "identity_unknown", "identity_changed", "management_protected", "preflight_failed",
    "plan_changed", "job_unknown", "job_conflict", "remote_uncertain", "health_unverified",
    "host_reboot_unproved", "package_impact_unproved", "guest_verification_unproved",
    "recovery_attestation_missing", "journal_unavailable", "command_unavailable",
    "dispatcher_unavailable", "configuration_invalid",
    "maintenance_policy_missing", "maintenance_guard_missing", "apt_configuration_changed",
    "package_origin_unsafe", "package_plan_unsafe", "package_health_unverified", "package_guard_unsafe",
    "package_action_failed", "no_package_changes", "maintenance_unavailable",
})


def decode_wire(payload):
    """Decode bounded JSON without duplicate keys or non-finite numeric values."""
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise PolicyError("wire_invalid")
            result[key] = value
        return result

    if not isinstance(payload, bytes) or len(payload) > MAX_WIRE:
        raise PolicyError("wire_invalid")
    try:
        return json.loads(payload, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(PolicyError("wire_invalid")))
    except (ValueError, UnicodeError, RecursionError):
        raise PolicyError("wire_invalid") from None


def protected_json(path):
    """Read only a regular root-owned config protected against non-root writes."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if info.st_uid != 0 or info.st_mode & 0o022 or not stat.S_ISREG(info.st_mode):
            raise PolicyError("configuration_invalid")
        for parent in Path(path).absolute().parents:
            info = parent.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise PolicyError("configuration_invalid")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return decode_wire(stream.read(MAX_WIRE + 1))
    finally:
        os.close(descriptor)


def run_bounded(argv, payload=b"", *, timeout=30, limit=MAX_WIRE, environment=None):
    """Execute an argument vector with a clean environment and bounded pipe IO."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=SAFE_ENV if environment is None else environment,
                               start_new_session=True)
    output, sent, total, completed = bytearray(), 0, 0, False
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    try:
        for stream in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "input")
        selector.register(process.stdout, selectors.EVENT_READ, "output")
        selector.register(process.stderr, selectors.EVENT_READ, "error")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PolicyError("command_unavailable")
            for key, _ in selector.select(min(remaining, 0.25)):
                if key.data == "input":
                    if sent == len(payload):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        sent += os.write(key.fd, payload[sent:sent + 4096])
                    continue
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                else:
                    total += len(chunk)
                    if total > limit:
                        raise PolicyError("command_unavailable")
                    if key.data == "output":
                        output.extend(chunk)
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise PolicyError("command_unavailable")
        completed = True
        return bytes(output)
    except (OSError, subprocess.SubprocessError):
        raise PolicyError("command_unavailable") from None
    finally:
        selector.close()
        if not completed:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            if not stream.closed:
                stream.close()


class SSHRemoteAdapter:
    """Use root-reviewed endpoint mappings; test runners replace only process IO."""

    @classmethod
    def from_file(cls, path):
        config = protected_json(path)
        for key in ("identity_file", "known_hosts"):
            info = os.stat(config[key], follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid not in {0, os.geteuid()}
                    or info.st_mode & 0o022 or key == "identity_file" and info.st_mode & 0o007):
                raise PolicyError("configuration_invalid")
            for parent in Path(config[key]).parents:
                info = parent.stat()
                if info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o022:
                    raise PolicyError("configuration_invalid")
        return cls(config)

    def __init__(self, config, *, runner=run_bounded):
        if (not isinstance(config, dict) or set(config) !=
                {"version", "identity_file", "known_hosts", "routing_db", "targets"}
                or config["version"] != 1 or not isinstance(config["targets"], dict)):
            raise PolicyError("configuration_invalid")
        for key in ("identity_file", "known_hosts", "routing_db"):
            value = config[key]
            if not isinstance(value, str) or not value.startswith("/") or "\n" in value or ".." in Path(value).parts:
                raise PolicyError("configuration_invalid")
        for target_id, endpoint in config["targets"].items():
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", target_id)
                    or not isinstance(endpoint, dict) or set(endpoint) != {"host", "user", "port"}
                    or not isinstance(endpoint["host"], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", endpoint["host"])
                    or not isinstance(endpoint["user"], str)
                    or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", endpoint["user"])
                    or type(endpoint["port"]) is not int or not 1 <= endpoint["port"] <= 65535):
                raise PolicyError("configuration_invalid")
        self.config, self.runner = json.loads(json.dumps(config)), runner
        path = Path(config["routing_db"])
        parent = path.parent.stat()
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
            raise PolicyError("journal_unavailable")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS routing (job TEXT PRIMARY KEY, target TEXT, digest TEXT)")

    def close(self):
        with self.lock:
            self.db.close()

    def _call(self, target_id, body):
        endpoint = self.config["targets"].get(target_id)
        if endpoint is None:
            raise PolicyError("target_unknown")
        options = ["BatchMode=yes", "IdentitiesOnly=yes", "IdentityAgent=none", "StrictHostKeyChecking=yes",
                   "GlobalKnownHostsFile=/dev/null", "UserKnownHostsFile=" + self.config["known_hosts"],
                   "UpdateHostKeys=no", "VerifyHostKeyDNS=no", "CanonicalizeHostname=no", "Tunnel=no",
                   "PasswordAuthentication=no", "KbdInteractiveAuthentication=no", "PreferredAuthentications=publickey",
                   "ForwardAgent=no", "ForwardX11=no", "ClearAllForwardings=yes", "ExitOnForwardFailure=yes",
                   "PermitLocalCommand=no", "ProxyCommand=none", "ProxyJump=none", "ControlMaster=no",
                   "ControlPath=none", "ControlPersist=no", "RequestTTY=no", "ConnectTimeout=10",
                   "ConnectionAttempts=1", "ServerAliveInterval=10", "ServerAliveCountMax=1"]
        argv = ["/usr/bin/ssh", "-F", "/dev/null", "-T", "-i", self.config["identity_file"]]
        for option in options:
            argv += ["-o", option]
        argv += ["-p", str(endpoint["port"]), "-l", endpoint["user"], "--", endpoint["host"], "codex-messaging-v1"]
        payload = json.dumps({"version": 1, **body}, separators=(",", ":")).encode()
        if len(payload) > MAX_WIRE:
            raise PolicyError("wire_invalid")
        try:
            value = decode_wire(self.runner(argv, payload, timeout=30, limit=MAX_WIRE))
            if (not isinstance(value, dict) or type(value.get("version")) is not int
                    or value["version"] != 1 or type(value.get("ok")) is not bool):
                raise PolicyError("wire_invalid")
            if value["ok"]:
                if set(value) != {"version", "ok", "result"}:
                    raise PolicyError("wire_invalid")
                return value["result"]
            if set(value) != {"version", "ok", "error_code"}:
                raise PolicyError("wire_invalid")
            code = value["error_code"]
            raise PolicyError(code if isinstance(code, str) and code in SAFE_REMOTE_ERRORS else "remote_rejected")
        except PolicyError:
            raise
        except Exception:
            raise PolicyError("remote_unavailable") from None

    def inspect(self, target, operation, parameters):
        return snapshot_from_wire(self._call(target.target_id, {
            "action": "inspect", "target_id": target.target_id, "operation": operation, "parameters": parameters}))

    def dispatch(self, job_id, plan):
        self._job_id(job_id)
        digest = plan_digest(plan)
        with self.lock:
            row = self.db.execute("SELECT target, digest FROM routing WHERE job=?", (job_id,)).fetchone()
            if row and row != (plan.target_id, digest):
                raise PolicyError("job_conflict")
            self.db.execute("INSERT OR IGNORE INTO routing VALUES (?, ?, ?)", (job_id, plan.target_id, digest))
        return self._result(self._call(plan.target_id, {
            "action": "dispatch", "job_id": job_id, "plan_digest": digest, "plan": plan_to_wire(plan)}))

    def query(self, job_id):
        self._job_id(job_id)
        with self.lock:
            row = self.db.execute("SELECT target FROM routing WHERE job=?", (job_id,)).fetchone()
        if row is None:
            return RemoteResult("unknown")
        return self._result(self._call(row[0], {"action": "query", "job_id": job_id}))

    @staticmethod
    def _job_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
            raise PolicyError("request_invalid")

    @staticmethod
    def _result(value):
        if (not isinstance(value, dict) or set(value) != {"state", "healthy", "boot_id", "diagnostics"}
                or not isinstance(value["state"], str) or value["state"] not in {"running", "verified", "failed", "unknown"}
                or type(value["healthy"]) is not bool
                or value["boot_id"] is not None and not isinstance(value["boot_id"], str)):
            raise PolicyError("wire_invalid")
        if not isinstance(value["diagnostics"], list) or any(not isinstance(pair, list) for pair in value["diagnostics"]):
            raise PolicyError("wire_invalid")
        return RemoteResult(value["state"], value["healthy"], value["boot_id"],
                            bounded_diagnostics(tuple(tuple(pair) for pair in value["diagnostics"])))
