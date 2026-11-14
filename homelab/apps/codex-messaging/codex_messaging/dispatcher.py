"""Serve one forced SSH protocol and supervise journalled reviewed target actions."""

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import sqlite3
import ssl
import stat
import sys
import time
import urllib.request
import urllib.parse

from .operations import (IDENTIFIER, PROOFS, PackageChange, PolicyError, Plan, RemoteResult, Snapshot,
                         Target, TargetRegistry, bounded_diagnostics, plan_digest, plan_from_wire, plan_to_wire)
from .remote import MAX_WIRE, decode_wire, protected_json, run_bounded

CONFIG_PATH = "/etc/codex-messaging/dispatcher.json"
ENTRY_PATH = "/opt/codex-messaging/entry.py"
JOB_ID = re.compile(r"[0-9a-f]{32}\Z")


def fixed_health(url):
    """Probe a fixed unauthenticated HTTP(S) endpoint; verify TLS and deny redirects."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise PolicyError("configuration_invalid")
    try:
        context = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                         urllib.request.HTTPSHandler(context=context)).open(url, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


class LiveProber:
    """Use fixed PVE/systemd probes; unavailable reboot/package proofs stay closed."""

    DEPENDENCIES = "Requires,Wants,PartOf,BindsTo,PropagatesStopTo,ConsistsOf,RequiredBy,BoundBy"

    def __init__(self, config, *, runner=run_bounded, reader=None, health_probe=fixed_health, package_runner=None):
        self.config, self.runner, self.health_probe = config, runner, health_probe
        self.reader = reader if reader is not None else lambda path: Path(path).read_text()
        from .maintenance import run_package
        self.package_runner = package_runner if package_runner is not None else run_package
        self._maintenance = None
        self._reboot = None

    def lxc_reboot(self):
        from .lxc_reboot import ApplicationLXCReboot
        if self._reboot is None:
            self._reboot = ApplicationLXCReboot(self.config, command=self.runner, reader=self.reader,
                                               identity=self._identity, health_probe=self.health_probe)
        return self._reboot

    def maintenance(self):
        from .maintenance import AptMaintenance
        if self._maintenance is None:
            self._maintenance = AptMaintenance(self.config, command=self._maintenance_command)
        return self._maintenance

    def _maintenance_command(self, target_id, argv, payload=b"", *, install=False):
        from .maintenance import PACKAGE_ENV
        target = self.config["targets"][target_id]
        command = ["/usr/bin/env", "-i", *[key + "=" + value for key, value in PACKAGE_ENV.items()], *argv]
        if target["kind"] == "lxc":
            command = ["/usr/sbin/pct", "exec", str(target["vmid"]), "--", *command]
        if install:
            return self.package_runner(command)
        return self.runner(command, payload, timeout=60, limit=MAX_WIRE)

    def _command(self, target, arguments):
        if target.kind == "lxc":
            arguments = ["/usr/sbin/pct", "exec", str(self.config["targets"][target.target_id]["vmid"]), "--", *arguments]
        return self.runner(arguments, timeout=20, limit=65536)

    def _identity(self, target):
        local_id = self.config["local_target_id"]
        local = self.config["targets"][local_id]
        if self.reader("/etc/machine-id").strip() != local["machine_id"]:
            raise PolicyError("identity_changed")
        resources = decode_wire(self.runner(["/usr/bin/pvesh", "get", "/cluster/resources", "--type", "vm",
                                             "--output-format", "json"], timeout=15, limit=MAX_WIRE))
        if not isinstance(resources, list) or any(not isinstance(item, dict) for item in resources):
            raise PolicyError("identity_unknown")
        management = self.config["targets"][self.config["management_target_id"]]
        matches = [item for item in resources if item.get("vmid") == management["vmid"] and item.get("type") == "qemu"]
        hosts = {value["pve_node"]: name for name, value in self.config["targets"].items() if value["kind"] == "host"}
        if len(matches) != 1 or matches[0].get("node") not in hosts:
            raise PolicyError("identity_unknown")
        management_host = hosts[matches[0]["node"]]
        registered = self.config["targets"][target.target_id]
        if target.kind == "host":
            if target.target_id != local_id:
                raise PolicyError("identity_changed")
        elif target.kind == "lxc":
            guests = [item for item in resources if item.get("vmid") == registered["vmid"]]
            if (len(guests) != 1 or guests[0].get("type") != "lxc" or guests[0].get("node") != local["pve_node"]
                    or guests[0].get("status") != "running"):
                raise PolicyError("identity_changed")
            identity = self._command(target, ["/usr/bin/cat", "/etc/machine-id"]).decode().strip()
            if identity != registered["machine_id"]:
                raise PolicyError("identity_changed")
        else:
            raise PolicyError("guest_verification_unproved")
        boot = (self._command(target, ["/usr/bin/cat", "/proc/sys/kernel/random/boot_id"]).decode().strip()
                if target.kind == "lxc" else self.reader("/proc/sys/kernel/random/boot_id").strip())
        if not isinstance(boot, str) or not IDENTIFIER.fullmatch(boot):
            raise PolicyError("identity_unknown")
        return management_host, boot

    def snapshot(self, target, operation, parameters):
        management_host, boot = self._identity(target)
        if operation == "host_reboot":
            raise PolicyError("host_reboot_unproved")
        if operation == "os_maintenance":
            if target.target_id not in self.config.get("maintenance_policies", {}):
                raise PolicyError("package_impact_unproved")
            context = self.maintenance().preview(target.target_id, self.config["targets"][target.target_id]["machine_id"],
                                                  boot, self.config["runbook_version"])
            return Snapshot(target.target_id, target.kind, self.config["management_target_id"], management_host,
                            self.config["runbook_version"], context["digest"], True,
                            package_changes=tuple(PackageChange(**p) for p in context["packages"]),
                            impact=("Any system service on this target may restart during package installation.",
                                    "Package configuration files retain their existing local values.",
                                    "Treat a separate reboot as required pending post-package operator review."),
                            verification=("Exact installed package versions and clean dpkg state", "All previously active services and registered health checks"),
                            preconditions=tuple(sorted(PROOFS[operation])), boot_id=boot, reboot_required=True)
        if operation == "guest_reboot":
            if target.kind != "lxc" or target.target_id not in self.config.get("reboot_policies", {}):
                raise PolicyError("guest_verification_unproved")
            return self.lxc_reboot().snapshot(target)
        proofs, impact, verification = (), (), ()
        version_input = [target.target_id, boot, operation]
        if operation == "service_restart":
            unit = parameters["unit"]
            policy = self.config["service_policies"].get(target.target_id, {}).get(unit)
            if (not isinstance(policy, dict) or set(policy) != {"dependency_digest", "impact", "health_url"}
                    or not isinstance(policy["impact"], list) or not policy["impact"]
                    or any(not isinstance(v, str) or not v.isprintable() or len(v) > 240 for v in policy["impact"])):
                raise PolicyError("preflight_failed")
            dependencies = self._command(target, ["/usr/bin/systemctl", "show", unit,
                                                  "--property=" + self.DEPENDENCIES, "--no-pager"])
            fingerprint = hashlib.sha256(dependencies).hexdigest()
            if fingerprint != policy["dependency_digest"]:
                raise PolicyError("preflight_failed")
            invocation = self._command(target, ["/usr/bin/systemctl", "show", unit, "--property=InvocationID", "--value"]).decode().strip()
            if not JOB_ID.fullmatch(invocation) or type(self.health_probe(policy["health_url"])) is not bool:
                raise PolicyError("health_unverified")
            version_input.extend([unit, invocation, fingerprint])
            proofs, impact, verification = tuple(PROOFS[operation]), tuple(policy["impact"]), ("Registered application health",)
        elif operation != "diagnose":
            raise PolicyError("operation_unsupported")
        return Snapshot(target.target_id, target.kind, self.config["management_target_id"], management_host,
                        self.config["runbook_version"], hashlib.sha256(json.dumps(version_input).encode()).hexdigest(),
                        operation == "service_restart", impact=impact, verification=verification,
                        preconditions=tuple(sorted(proofs)), boot_id=boot)

    def execute(self, plan, job_id=None):
        if plan.operation == "diagnose":
            return
        if plan.operation == "os_maintenance":
            return self.maintenance().execute(plan, job_id)
        if plan.operation == "guest_reboot":
            return self.lxc_reboot().execute(plan)
        if plan.operation != "service_restart":
            raise PolicyError("operation_unsupported")
        target = Target(plan.target_id, plan.target_kind)
        self._command(target, ["/usr/bin/systemctl", "restart", dict(plan.parameters)["unit"]])

    def verify(self, plan):
        target = Target(plan.target_id, plan.target_kind)
        if plan.operation == "guest_reboot":
            return self.lxc_reboot().verify(plan)
        if plan.operation == "os_maintenance":
            _management_host, boot = self._identity(target)
            healthy = boot == plan.snapshot.boot_id and self.maintenance().verify(plan)
            if healthy:
                for unit in self.config["maintenance_policies"][plan.target_id]["verification_units"]:
                    policy = self.config["service_policies"].get(plan.target_id, {}).get(unit)
                    if policy and self.health_probe(policy["health_url"]) is not True:
                        healthy = False
            return healthy, boot
        current = self.snapshot(target, plan.operation, dict(plan.parameters))
        if plan.operation == "diagnose":
            return True, current.boot_id
        policy = self.config["service_policies"][plan.target_id][dict(plan.parameters)["unit"]]
        return current.plan_version != plan.snapshot.plan_version and self.health_probe(policy["health_url"]) is True, current.boot_id

    def diagnostics(self, plan):
        target = Target(plan.target_id, plan.target_kind)
        probe = dict(plan.parameters).get("probe", "health")
        if probe in {"health", "reboot"}:
            _, boot = self._identity(target)
            selected = [("identity", "verified"), ("boot_id", boot)]
            for index, unit in enumerate(self.config["targets"][target.target_id]["units"][:12]):
                state = self._command(target, ["/usr/bin/systemctl", "show", unit, "--property=ActiveState", "--value"]).decode().strip()
                if state not in {"active", "reloading", "inactive", "failed", "activating", "deactivating", "maintenance", "refreshing"}:
                    raise PolicyError("command_unavailable")
                selected.append(("unit_" + str(index), unit + ": " + state))
            return tuple(selected)
        if probe == "resources":
            value = self._command(target, ["/usr/bin/cat", "/proc/loadavg"]).decode().split()
            if len(value) < 3 or any(not re.fullmatch(r"[0-9]+\.[0-9]+", item) for item in value[:3]):
                raise PolicyError("command_unavailable")
            return (("load_1m", value[0]), ("load_5m", value[1]), ("load_15m", value[2]))
        if probe == "packages":
            output = self._command(target, ["/usr/bin/dpkg", "--audit"])
            return (("package_database", "clean" if not output.strip() else "operator_review_required"),)
        if probe == "unit_logs":
            unit = dict(plan.parameters)["unit"]
            output = self._command(target, ["/usr/bin/journalctl", "--unit=" + unit, "--lines=50", "--priority=warning", "--quiet", "--output=json"])
            return (("recent_warning_records", str(len(output.splitlines()))),)
        raise PolicyError("operation_unsupported")


class Dispatcher:
    """Production uses from_file; injected probes/supervisors are offline test seams."""

    @classmethod
    def from_file(cls, path=CONFIG_PATH):
        if path != CONFIG_PATH or os.geteuid() != 0:
            raise PolicyError("configuration_invalid")
        config = protected_json(path)
        state = Path(config["state_dir"]).stat()
        if state.st_uid != 0 or state.st_mode & 0o077:
            raise PolicyError("configuration_invalid")
        return cls(config)

    def __init__(self, config, *, prober=None, supervisor=None, job_active=None):
        base_keys = {"version", "state_dir", "local_target_id", "management_target_id", "runbook_version", "targets", "service_policies"}
        if (not isinstance(config, dict) or not base_keys <= set(config) <= base_keys | {"maintenance_policies", "reboot_policies"}
                or config["version"] != 1):
            raise PolicyError("configuration_invalid")
        self.config = json.loads(json.dumps(config))
        targets = []
        for name, value in config["targets"].items():
            if (not isinstance(value, dict) or set(value) !=
                    {"kind", "machine_id", "pve_node", "vmid", "units", "operations"}
                    or not isinstance(value["machine_id"], str)
                    or not re.fullmatch(r"[0-9a-f]{32}", value["machine_id"])
                    or value["kind"] == "host" and
                       (value["vmid"] is not None or not isinstance(value["pve_node"], str)
                        or not IDENTIFIER.fullmatch(value["pve_node"]))
                    or value["kind"] != "host" and
                       (type(value["vmid"]) is not int or not 100 <= value["vmid"] <= 999999999)):
                raise PolicyError("configuration_invalid")
            targets.append(Target(name, value["kind"], units=tuple(value["units"]), operations=tuple(value["operations"])))
        self.registry = TargetRegistry(targets)
        host_nodes = [value["pve_node"] for value in config["targets"].values() if value["kind"] == "host"]
        guest_ids = [value["vmid"] for value in config["targets"].values() if value["kind"] != "host"]
        if (len(set(host_nodes)) != len(host_nodes) or len(set(guest_ids)) != len(guest_ids)
                or not isinstance(config["runbook_version"], str) or not IDENTIFIER.fullmatch(config["runbook_version"])):
            raise PolicyError("configuration_invalid")
        if (self.registry.resolve(config["local_target_id"]).kind != "host"
                or self.registry.resolve(config["management_target_id"]).kind != "vm"):
            raise PolicyError("configuration_invalid")
        path = Path(config["state_dir"])
        info = path.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077 or not stat.S_ISDIR(info.st_mode):
            raise PolicyError("journal_unavailable")
        database = path / "jobs.sqlite"
        descriptor = os.open(database, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        self.db = sqlite3.connect(database, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, digest TEXT, plan TEXT, "
                        "state TEXT, launched INTEGER DEFAULT 0)")
        if "diagnostics" not in {row[1] for row in self.db.execute("PRAGMA table_info(jobs)")}:
            self.db.execute("ALTER TABLE jobs ADD COLUMN diagnostics TEXT NOT NULL DEFAULT '[]'")
        self.prober = prober if prober is not None else LiveProber(self.config)
        self.supervisor = supervisor if supervisor is not None else self._supervise
        self.job_active = job_active if job_active is not None else self._job_active

    def close(self):
        if isinstance(self.prober, LiveProber) and self.prober._maintenance is not None:
            self.prober._maintenance.close()
        self.db.close()

    def _plan(self, target_id, operation, parameters):
        target = self.registry.resolve(target_id)
        if target.target_id != target_id or operation not in target.operations:
            raise PolicyError("operation_unsupported")
        if not isinstance(parameters, dict) or any(not isinstance(v, str) for v in parameters.values()):
            raise PolicyError("parameters_invalid")
        if operation == "service_restart":
            valid = set(parameters) == {"unit"} and parameters["unit"] in target.units
        else:
            valid = not parameters
            if operation == "diagnose":
                valid = valid or set(parameters) == {"probe"} and parameters["probe"] in {"health", "resources", "packages", "reboot", "dns"}
                valid = valid or set(parameters) == {"probe", "unit"} and parameters["probe"] == "unit_logs" and parameters["unit"] in target.units
        if not valid:
            raise PolicyError("parameters_invalid")
        snapshot = self.prober.snapshot(target, operation, parameters)
        if (snapshot.target_id, snapshot.target_kind) != (target.target_id, target.kind):
            raise PolicyError("identity_changed")
        management = self.registry.resolve(snapshot.management_target_id)
        host = self.registry.resolve(snapshot.management_host_id)
        if (management.target_id != self.config["management_target_id"] or management.kind != "vm"
                or host.target_id != snapshot.management_host_id or host.kind != "host"):
            raise PolicyError("identity_unknown")
        for name in snapshot.affected_target_ids:
            if self.registry.resolve(name).target_id != name:
                raise PolicyError("identity_unknown")
        if operation != "diagnose":
            if (management.target_id in (target_id, *snapshot.affected_target_ids)
                    or operation.endswith("reboot") and host.target_id in (target_id, *snapshot.affected_target_ids)):
                raise PolicyError("management_protected")
            if snapshot.preflight_verified is not True or not PROOFS[operation] <= set(snapshot.preconditions):
                raise PolicyError("preflight_failed")
        return Plan(target_id, target.kind, operation, tuple(sorted(parameters.items())), snapshot)

    def handle(self, original_command, payload):
        try:
            if original_command != "codex-messaging-v1":
                raise PolicyError("request_invalid")
            request = decode_wire(payload)
            if not isinstance(request, dict) or type(request.get("version")) is not int or request["version"] != 1:
                raise PolicyError("request_invalid")
            action = request.get("action")
            if action == "inspect" and set(request) == {"version", "action", "target_id", "operation", "parameters"}:
                result = asdict(self._plan(request["target_id"], request["operation"], request["parameters"]).snapshot)
            elif action == "dispatch" and set(request) == {"version", "action", "job_id", "plan_digest", "plan"}:
                result = asdict(self.dispatch(request["job_id"], request["plan_digest"], plan_from_wire(request["plan"])))
            elif action == "query" and set(request) == {"version", "action", "job_id"}:
                result = asdict(self.query(request["job_id"]))
            else:
                raise PolicyError("request_invalid")
            return {"version": 1, "ok": True, "result": result}
        except PolicyError as error:
            return {"version": 1, "ok": False, "error_code": error.code}
        except Exception:
            return {"version": 1, "ok": False, "error_code": "dispatcher_unavailable"}

    def dispatch(self, job_id, digest, plan):
        self._job_id(job_id)
        if not isinstance(digest, str) or digest != plan_digest(plan):
            raise PolicyError("plan_changed")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row:
                if row["digest"] != digest:
                    raise PolicyError("job_conflict")
                self.db.execute("COMMIT")
                return self.query(job_id)
            if tuple(sorted(dict(plan.parameters).items())) != plan.parameters:
                raise PolicyError("parameters_invalid")
            current = self._plan(plan.target_id, plan.operation, dict(plan.parameters))
            if plan_digest(current) != digest:
                raise PolicyError("plan_changed")
            self.db.execute("INSERT INTO jobs (id,digest,plan,state,launched) VALUES (?, ?, ?, 'queued', 0)",
                            (job_id, digest, json.dumps(plan_to_wire(plan), separators=(",", ":"))))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        try:
            self.supervisor(job_id)
            self.db.execute("UPDATE jobs SET launched=1 WHERE id=?", (job_id,))
        except Exception:
            return RemoteResult("unknown")
        return RemoteResult("running")

    def run(self, job_id):
        self._job_id(job_id)
        self.db.execute("BEGIN IMMEDIATE")
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["state"] != "queued":
            self.db.execute("ROLLBACK")
            return
        self.db.execute("UPDATE jobs SET state='running', launched=1 WHERE id=?", (job_id,))
        self.db.execute("COMMIT")
        plan = plan_from_wire(json.loads(row["plan"]))
        try:
            current = self._plan(plan.target_id, plan.operation, dict(plan.parameters))
            if plan_digest(current) != row["digest"]:
                self.db.execute("UPDATE jobs SET state='failed' WHERE id=?", (job_id,))
                return
            if plan.operation == "os_maintenance":
                self.prober.execute(plan, job_id=job_id)
            else:
                self.prober.execute(plan)
            healthy, boot = self.prober.verify(plan)
            verified = healthy is True and (not plan.operation.endswith("reboot") or boot and boot != plan.snapshot.boot_id)
            diagnostics = bounded_diagnostics(self.prober.diagnostics(plan)) if plan.operation == "diagnose" else ()
            self.db.execute("UPDATE jobs SET state=?, diagnostics=? WHERE id=?", ("verified" if verified else "unknown", json.dumps(diagnostics), job_id))
        except Exception:
            self.db.execute("UPDATE jobs SET state='unknown' WHERE id=?", (job_id,))

    def query(self, job_id):
        self._job_id(job_id)
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return RemoteResult("unknown")
        plan = plan_from_wire(json.loads(row["plan"]))
        if row["state"] in {"running", "unknown", "verified"}:
            active = self.job_active(job_id)
            if active is True:
                return RemoteResult("running")
            if active is not False:
                return RemoteResult("unknown")
            healthy, boot = self.prober.verify(plan)
            if healthy is True and (not plan.operation.endswith("reboot") or boot and boot != plan.snapshot.boot_id):
                diagnostics = bounded_diagnostics(tuple(tuple(pair) for pair in json.loads(row["diagnostics"])))
                if plan.operation == "diagnose" and not diagnostics:
                    diagnostics = bounded_diagnostics(self.prober.diagnostics(plan))
                self.db.execute("UPDATE jobs SET state='verified', diagnostics=? WHERE id=?", (json.dumps(diagnostics), job_id))
                return RemoteResult("verified", healthy=True, boot_id=boot, diagnostics=diagnostics)
            return RemoteResult("unknown" if row["state"] != "running" else "running")
        if row["state"] == "queued":
            return RemoteResult("running" if row["launched"] else "unknown")
        return RemoteResult("failed")

    @staticmethod
    def _job_id(value):
        if not isinstance(value, str) or not JOB_ID.fullmatch(value):
            raise PolicyError("request_invalid")

    @staticmethod
    def _job_active(job_id):
        try:
            output = run_bounded(["/usr/bin/systemctl", "show", "codex-messaging-job-" + job_id + ".service",
                                  "--property=ActiveState", "--value", "--no-pager"], timeout=10, limit=1024).decode().strip()
            if output in {"active", "activating", "deactivating", "reloading"}:
                return True
            if output in {"inactive", "failed", ""}:
                return False
        except Exception:
            pass
        return None

    @staticmethod
    def _supervise(job_id):
        run_bounded(["/usr/bin/systemd-run", "--quiet", "--no-block", "--collect",
                     "--unit=codex-messaging-job-" + job_id, "--property=Type=exec",
                     "--property=User=root", "--property=UMask=0077", "--property=WorkingDirectory=/",
                     "--property=NoNewPrivileges=yes", "--property=ProtectHome=yes", "--property=PrivateTmp=yes",
                     "--property=RuntimeMaxSec=infinity", "--property=TimeoutStopSec=infinity", "--property=KillMode=process",
                     "/usr/bin/python3", "-I", ENTRY_PATH,
                     "dispatcher", "run", "--config", CONFIG_PATH, "--job", job_id], timeout=15)


def read_request(stream):
    """Bound request bytes and time even if an authenticated peer withholds EOF."""
    payload = bytearray()
    deadline = time.monotonic() + 15
    selector = selectors.DefaultSelector()
    try:
        selector.register(stream, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise PolicyError("request_invalid")
            part = os.read(stream.fileno(), min(65536, MAX_WIRE + 1 - len(payload)))
            if not part:
                return bytes(payload)
            payload.extend(part)
            if len(payload) > MAX_WIRE:
                raise PolicyError("request_invalid")
    finally:
        selector.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("serve", "run"))
    parser.add_argument("--config", default=CONFIG_PATH)
    parser.add_argument("--job")
    arguments = parser.parse_args(argv)
    dispatcher = None
    try:
        if arguments.action == "serve" and os.environ.get("SSH_ORIGINAL_COMMAND") != "codex-messaging-v1":
            raise PolicyError("request_invalid")
        dispatcher = Dispatcher.from_file(arguments.config)
        if arguments.action == "run":
            dispatcher.run(arguments.job)
            return 0
        result = dispatcher.handle("codex-messaging-v1", read_request(sys.stdin.buffer))
    except PolicyError as error:
        result = {"version": 1, "ok": False, "error_code": error.code}
    except Exception:
        result = {"version": 1, "ok": False, "error_code": "dispatcher_unavailable"}
    finally:
        if dispatcher is not None:
            dispatcher.close()
    payload = json.dumps(result, separators=(",", ":")).encode()
    if len(payload) > MAX_WIRE:
        payload = b'{"version":1,"ok":false,"error_code":"dispatcher_unavailable"}'
    sys.stdout.buffer.write(payload + b"\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
