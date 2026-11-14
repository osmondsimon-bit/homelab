"""Prepare exact OS-only apt transactions and guard supervised package actions."""

from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import time

from .remote import run_bounded

from .operations import PackageChange, PolicyError

PACKAGE = r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?"
VERSION = r"[0-9][A-Za-z0-9.+:~_-]{0,127}"
INSTALL = re.compile(rf"Inst ({PACKAGE})(?: \[({VERSION})\])? \(({VERSION}) [^()\n]+ \[([a-z0-9]+)\]\)\Z")
CONFIGURE = re.compile(rf"Conf ({PACKAGE}) \(({VERSION}) [^()\n]+ \[[a-z0-9]+\]\)\Z")
SUMMARY = re.compile(r"([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded\.\Z")
HEADINGS = frozenset({"Reading package lists... Done", "Reading package lists...", "Building dependency tree... Done",
                      "Building dependency tree...", "Reading state information... Done", "Reading state information...",
                      "The following additional packages will be installed:", "The following NEW packages will be installed:",
                      "The following packages will be upgraded:", "The following packages have been kept back:",
                      "Suggested packages:", "Recommended packages:"})
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
GUARD_STATE = "/var/lib/codex-messaging-apt"
ENTRY_PATH = "/opt/codex-messaging/entry.py"
OPTIONS = ["--no-remove", "--no-install-recommends", "-oDpkg::Use-Pty=0", "-oAPT::Color=0",
           "-oAcquire::AllowInsecureRepositories=false", "-oAcquire::AllowDowngradeToInsecureRepositories=false",
           "-oAPT::Get::AllowUnauthenticated=false", "-oAPT::Get::AutomaticRemove=false",
           "-oAPT::Get::allow-downgrades=false", "-oAPT::Get::allow-change-held-packages=false",
           "-oAPT::Get::allow-remove-essential=false"]
PACKAGE_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/nonexistent",
               "DEBIAN_FRONTEND": "noninteractive", "UCF_FORCE_CONFFOLD": "1", "NEEDRESTART_MODE": "l",
               "APT_LISTCHANGES_FRONTEND": "none"}


def run_package(argv):
    """Wait for a supervised package action without timeout or child termination."""
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=PACKAGE_ENV)
        if process.wait() != 0:
            raise PolicyError("package_action_failed")
        return b""
    except OSError:
        raise PolicyError("package_action_failed") from None


def package_idle():
    """Never verify completion while apt/dpkg still holds its actual target locks."""
    descriptors = []
    try:
        for path in ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock"):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                return False
            fcntl.lockf(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return True
    except OSError:
        return False
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def secure_database(directory, name):
    path = Path(directory)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise PolicyError("journal_unavailable")
    descriptor = os.open(path / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
            raise PolicyError("journal_unavailable")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    database = sqlite3.connect(path / name, isolation_level=None)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA synchronous=FULL")
    return database


def helper_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def local_identity():
    return Path("/etc/machine-id").read_text().strip(), Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def archive_metadata(path):
    value = Path(path)
    if value.parent != Path("/var/cache/apt/archives") or value.resolve() != value.absolute():
        raise PolicyError("package_guard_unsafe")
    for parent in value.parents:
        info = parent.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise PolicyError("package_guard_unsafe")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PolicyError("package_guard_unsafe")
    finally:
        os.close(descriptor)
    fields = deb822(run_bounded(["/usr/bin/dpkg-deb", "--field", path, "Package", "Version", "Architecture"], timeout=10))
    if len(fields) != 1 or set(fields[0]) != {"Package", "Version", "Architecture"}:
        raise PolicyError("package_guard_unsafe")
    return fields[0]["Package"], fields[0]["Version"], fields[0]["Architecture"]


class GuardJournal:
    """Root helper stores one immutable expected transaction for the original job."""

    def __init__(self, state_dir=GUARD_STATE, *, artifact_reader=archive_metadata,
                 machine_reader=local_identity, configuration_reader=None, digest_reader=helper_digest,
                 audit_reader=None):
        self.db = secure_database(state_dir, "guard.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS guards (job TEXT PRIMARY KEY, digest TEXT, context TEXT, used INTEGER)")
        self.artifact_reader, self.machine_reader, self.digest_reader = artifact_reader, machine_reader, digest_reader
        self.configuration_reader = configuration_reader or (lambda: hashlib.sha256(run_bounded(["/usr/bin/apt-config", "dump"])).hexdigest())
        self.audit_reader = audit_reader or (lambda: run_bounded(["/usr/bin/dpkg", "--audit"]))

    def close(self):
        self.db.close()

    @staticmethod
    def _validate(job_id, context):
        from .operations import IDENTIFIER
        expected = {"version", "job_id", "target_id", "machine_id", "boot_id", "runbook_version",
                    "transaction_digest", "apt_configuration_digest", "guard_digest", "packages"}
        if (not isinstance(job_id, str) or not HEX32.fullmatch(job_id) or not isinstance(context, dict)
                or set(context) != expected or type(context["version"]) is not int or context["version"] != 1
                or context["job_id"] != job_id or not isinstance(context["packages"], list)
                or not 1 <= len(context["packages"]) <= 4096
                or any(not isinstance(context[k], str) or not IDENTIFIER.fullmatch(context[k])
                       for k in ("target_id", "boot_id", "runbook_version"))
                or not isinstance(context["machine_id"], str) or not HEX32.fullmatch(context["machine_id"])
                or any(not isinstance(context[k], str) or not HEX64.fullmatch(context[k])
                       for k in ("transaction_digest", "apt_configuration_digest", "guard_digest"))):
            raise PolicyError("package_guard_unsafe")
        for package in context["packages"]:
            if (not isinstance(package, list) or len(package) != 3
                    or any(not isinstance(v, str) for v in package)
                    or not re.fullmatch(PACKAGE, package[0]) or not re.fullmatch(VERSION, package[1])
                    or not re.fullmatch(r"[a-z0-9]+", package[2])):
                raise PolicyError("package_guard_unsafe")
        if len({(p[0], p[2]) for p in context["packages"]}) != len(context["packages"]):
            raise PolicyError("package_guard_unsafe")

    def prepare(self, job_id, context):
        self._validate(job_id, context)
        if self.machine_reader() != (context["machine_id"], context["boot_id"]) or self.digest_reader() != context["guard_digest"]:
            raise PolicyError("identity_changed")
        digest = canonical_digest(context)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT digest,used FROM guards WHERE job=?", (job_id,)).fetchone()
            if row and (row["digest"] != digest or row["used"]):
                raise PolicyError("job_conflict")
            self.db.execute("INSERT OR IGNORE INTO guards VALUES (?, ?, ?, 0)", (job_id, digest, json.dumps(context)))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def verify(self, job_id, payload):
        if not isinstance(job_id, str) or not HEX32.fullmatch(job_id) or not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
            raise PolicyError("package_guard_unsafe")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM guards WHERE job=?", (job_id,)).fetchone()
            if row is None or row["used"]:
                raise PolicyError("job_conflict")
            context = json.loads(row["context"])
            if (canonical_digest(context) != row["digest"]
                    or self.machine_reader() != (context["machine_id"], context["boot_id"])
                    or self.digest_reader() != context["guard_digest"]
                    or self.configuration_reader() != context["apt_configuration_digest"] or self.audit_reader().strip()):
                raise PolicyError("package_guard_unsafe")
            paths = payload.decode("ascii").splitlines()
            if not paths or len(set(paths)) != len(paths) or len(paths) > 4096:
                raise PolicyError("package_guard_unsafe")
            actual = []
            for value in paths:
                path = Path(value)
                if (path.parent != Path("/var/cache/apt/archives") or path.name in {"", ".", ".."}
                        or not re.fullmatch(r"[A-Za-z0-9_.:+%~-]+\.deb", path.name)):
                    raise PolicyError("package_guard_unsafe")
                name, version, architecture = self.artifact_reader(value)
                actual.append([name, version, architecture])
            if sorted(actual) != sorted(context["packages"]):
                raise PolicyError("package_guard_unsafe")
            self.db.execute("UPDATE guards SET used=1 WHERE job=?", (job_id,))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise


def parse_simulation(payload):
    """Accept only complete LANG=C simulations with matched Inst/Conf/counts."""
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise PolicyError("package_plan_unsafe")
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeError:
        raise PolicyError("package_plan_unsafe") from None
    installs, configured, summary = {}, set(), None
    package_list = False
    for line in lines:
        if not line:
            continue
        if line in HEADINGS:
            package_list = line.endswith(":")
            continue
        if line.startswith("  ") and package_list and all(re.fullmatch(PACKAGE, item) for item in line.split()):
            continue
        package_list = False
        match = INSTALL.fullmatch(line)
        if match:
            name, current, candidate, _architecture = match.groups()
            if name in installs or current == candidate or len(installs) >= 4096:
                raise PolicyError("package_plan_unsafe")
            installs[name] = PackageChange(name, current or "", candidate, "upgrade" if current else "install")
            continue
        match = CONFIGURE.fullmatch(line)
        if match:
            name, version = match.groups()
            if name not in installs or name in configured or installs[name].candidate != version:
                raise PolicyError("package_plan_unsafe")
            configured.add(name)
            continue
        match = SUMMARY.fullmatch(line)
        if match and summary is None:
            summary = tuple(int(value) for value in match.groups())
            continue
        if re.fullmatch(rf"{PACKAGE} is already the newest version \({VERSION}\)\.", line):
            continue
        if re.fullmatch(r"(?:Need to get [0-9.,]+ [kMGT]?B of archives\.|After this operation, [0-9.,]+ [kMGT]?B (?:of additional disk space will be used|disk space will be freed)\.)", line):
            continue
        raise PolicyError("package_plan_unsafe")
    upgrades = sum(item.action == "upgrade" for item in installs.values())
    new = len(installs) - upgrades
    if summary is None or summary[:3] != (upgrades, new, 0) or configured != set(installs):
        raise PolicyError("package_plan_unsafe")
    return tuple(installs[name] for name in sorted(installs))


def deb822(payload):
    """Read bounded simple metadata records; ambiguous repeated fields fail closed."""
    if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
        raise PolicyError("package_origin_unsafe")
    try:
        text = payload.decode("utf-8")
    except UnicodeError:
        raise PolicyError("package_origin_unsafe") from None
    records, record = [], {}
    for line in text.splitlines() + [""]:
        if not line:
            if record:
                records.append(record)
                record = {}
            continue
        match = re.fullmatch(r"([A-Za-z0-9-]+): (.*)", line)
        if not match or match[1] in record:
            raise PolicyError("package_origin_unsafe")
        record[match[1]] = match[2]
    return records


def validate_origins(changes, indexes, package_policies, policy):
    """Require an explicit OS classification and authenticated allowed distro indexes."""
    sources = {}
    for record in deb822(indexes):
        if record.get("Identifier") != "Packages":
            continue
        fields = {"Description", "Origin", "Codename", "Component", "Architecture", "Trusted"}
        if not fields <= set(record) or record["Description"] in sources:
            raise PolicyError("package_origin_unsafe")
        sources[record["Description"]] = record
    architectures = []
    for change in changes:
        base = change.name.split(":")[0]
        if (change.name not in policy["reviewed_os_packages"] or change.name in policy["denied_packages"]
                or "firmware" in base or base in {"codex-messaging", "codex-cli", "tailscale", "openssh-server", "openssh-client", "sudo"}):
            raise PolicyError("package_origin_unsafe")
        text = package_policies[change.name]
        if not isinstance(text, str) or len(text) > 65536:
            raise PolicyError("package_origin_unsafe")
        lines = text.splitlines()
        if (not lines or lines[0] != change.name + ":"
                or "  Installed: " + (change.current or "(none)") not in lines
                or "  Candidate: " + change.candidate not in lines):
            raise PolicyError("package_origin_unsafe")
        selected, matched, candidate_sources = False, 0, []
        for line in lines[1:]:
            version = re.fullmatch(rf"\s+(?:\*\*\* )?({VERSION})\s+-?[0-9]+", line)
            if version:
                selected = version[1] == change.candidate
                matched += selected
                continue
            location = re.fullmatch(r"\s+[0-9]+ (.+ Packages)", line)
            if selected and location:
                candidate_sources.append(location[1])
        if matched != 1 or not candidate_sources:
            raise PolicyError("package_origin_unsafe")
        arches = set()
        for location in candidate_sources:
            record = sources.get(location)
            if (record is None or record["Trusted"] != "yes" or record["Origin"] not in policy["allowed_origins"]
                    or record["Codename"] not in policy["allowed_codenames"] or record["Component"] != "main"
                    or not re.fullmatch(r"[a-z0-9]+", record["Architecture"])):
                raise PolicyError("package_origin_unsafe")
            arches.add(record["Architecture"])
        if len(arches) != 1:
            raise PolicyError("package_origin_unsafe")
        architectures.append((change.name, arches.pop()))
    return tuple(architectures)


class AptMaintenance:
    """Read live apt facts and require a transaction-specific attended recovery grant."""

    def __init__(self, config, *, command, clock=time.time):
        self.config, self.command, self.clock = config, command, clock
        self.db = secure_database(config["state_dir"], "attestations.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS attestations (digest TEXT PRIMARY KEY, context TEXT, "
                        "issued REAL, expires REAL, evidence TEXT, consumed_by TEXT)")

    def close(self):
        self.db.close()

    def _policy(self, target):
        if self.config["targets"][target]["kind"] not in {"host", "lxc"}:
            raise PolicyError("operation_unsupported")
        policy = self.config.get("maintenance_policies", {}).get(target)
        keys = {"reviewed_os_packages", "allowed_origins", "allowed_codenames", "denied_packages",
                "verification_units", "apt_configuration_digest", "guard_digest"}
        if not isinstance(policy, dict) or set(policy) != keys:
            raise PolicyError("maintenance_policy_missing")
        for key in ("reviewed_os_packages", "denied_packages"):
            if (not isinstance(policy[key], list) or len(policy[key]) > 4096
                    or any(not isinstance(v, str) or not re.fullmatch(PACKAGE, v) for v in policy[key])):
                raise PolicyError("maintenance_policy_missing")
        if (not policy["reviewed_os_packages"] or not policy["verification_units"]
                or not set(policy["verification_units"]) <= set(self.config["targets"][target]["units"])
                or not isinstance(policy["allowed_origins"], list) or not policy["allowed_origins"]
                or not set(policy["allowed_origins"]) <= {"Debian", "Ubuntu"}
                or not isinstance(policy["allowed_codenames"], list) or not policy["allowed_codenames"]
                or any(not isinstance(v, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", v) for v in policy["allowed_codenames"])
                or any(not isinstance(policy[k], str) or not HEX64.fullmatch(policy[k])
                       for k in ("apt_configuration_digest", "guard_digest"))):
            raise PolicyError("maintenance_policy_missing")
        return policy

    def _services(self, target):
        payload = self.command(target, ["/usr/bin/systemctl", "show", "*.service", "--all",
                                        "--property=Id,ActiveState,Type,Transient,FragmentPath", "--no-pager"])
        if not isinstance(payload, bytes) or len(payload) > 1024 * 1024:
            raise PolicyError("package_health_unverified")
        records, current = [], {}
        try:
            lines = payload.decode("ascii").splitlines()
        except UnicodeError:
            raise PolicyError("package_health_unverified") from None
        for line in lines + [""]:
            if not line:
                if current:
                    records.append(current)
                    current = {}
                continue
            key, separator, value = line.partition("=")
            if not separator or key not in {"Id", "ActiveState", "Type", "Transient", "FragmentPath"} or key in current:
                raise PolicyError("package_health_unverified")
            current[key] = value
        if not records or len(records) > 4096:
            raise PolicyError("package_health_unverified")
        services = {}
        for value in records:
            if (set(value) != {"Id", "ActiveState", "Type", "Transient", "FragmentPath"}
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@\\-]{0,239}\.service", value["Id"])
                    or value["Id"] in services or value["ActiveState"] not in
                    {"active", "inactive", "activating", "deactivating", "reloading"}
                    or value["Type"] not in {"simple", "exec", "forking", "oneshot", "dbus", "notify", "notify-reload", "idle"}):
                raise PolicyError("package_health_unverified")
            if re.fullmatch(r"codex-messaging-job-[0-9a-f]{32}\.service", value["Id"]) and value["Transient"] == "yes":
                fragment = "/run/systemd/transient/" + value["Id"]
                if value["FragmentPath"] == fragment:
                    metadata = self.command(target, ["/usr/bin/stat", "--format=%u:%a:%F", "--", fragment]).decode().strip()
                    match = re.fullmatch(r"0:([0-7]{3,4}):regular file", metadata)
                    if match and not int(match[1], 8) & 0o022:
                        continue
            services[value["Id"]] = {"type": value["Type"], "active": value["ActiveState"]}
        return services

    def preview(self, target, machine, boot, runbook, *, require_attestation=True):
        from .remote import decode_wire
        policy = self._policy(target)
        identity = decode_wire(self.command(target, ["/usr/bin/python3", "-I", ENTRY_PATH, "maintenance", "identity"]))
        if (not isinstance(identity, dict) or set(identity) != {"version", "machine_id", "boot_id", "guard_digest"}
                or type(identity["version"]) is not int or identity["version"] != 1
                or identity["machine_id"] != machine or identity["boot_id"] != boot
                or identity["guard_digest"] != policy["guard_digest"]):
            raise PolicyError("maintenance_guard_missing")
        configuration = self.command(target, ["/usr/bin/apt-config", "dump"])
        if hashlib.sha256(configuration).hexdigest() != policy["apt_configuration_digest"]:
            raise PolicyError("apt_configuration_changed")
        if self.command(target, ["/usr/bin/dpkg", "--audit"]).strip():
            raise PolicyError("package_health_unverified")
        output = self.command(target, ["/usr/bin/apt-get", *OPTIONS, "--simulate", "install", *sorted(policy["reviewed_os_packages"])])
        changes = parse_simulation(output)
        if not changes:
            raise PolicyError("no_package_changes")
        policies = {p.name: self.command(target, ["/usr/bin/apt-cache", "policy", p.name]).decode() for p in changes}
        index_arches = dict(validate_origins(changes, self.command(target, ["/usr/bin/apt-get", "indextargets"]), policies, policy))
        architectures = {}
        for line in output.decode("ascii").splitlines():
            match = INSTALL.fullmatch(line)
            if match:
                architectures[match[1]] = match[4]
        if any(architectures[p.name] not in {index_arches[p.name], "all"} for p in changes):
            raise PolicyError("package_origin_unsafe")
        for change in changes:
            if change.current:
                try:
                    self.command(target, ["/usr/bin/dpkg", "--compare-versions", change.candidate, "gt", change.current])
                except Exception:
                    raise PolicyError("package_plan_unsafe") from None
        services = self._services(target)
        if not set(policy["verification_units"]) <= {name for name, state in services.items() if state["active"] == "active"}:
            raise PolicyError("package_health_unverified")
        context = {"target_id": target, "machine_id": machine, "boot_id": boot, "runbook_version": runbook,
                   "packages": [asdict(p) for p in changes], "architectures": architectures,
                   "services": sorted((name, state["type"]) for name, state in services.items()),
                   "active_units": sorted(name for name, state in services.items() if state["active"] == "active" and state["type"] != "oneshot"),
                   "verification_units": sorted(policy["verification_units"]),
                   "apt_configuration_digest": policy["apt_configuration_digest"], "guard_digest": policy["guard_digest"]}
        context["digest"] = canonical_digest(context)
        if require_attestation:
            self._grant(context["digest"])
        return context

    def _grant(self, digest, *, job_id=None):
        row = self.db.execute("SELECT * FROM attestations WHERE digest=?", (digest,)).fetchone()
        if (row is None or not row["issued"] <= self.clock() < row["expires"]
                or row["expires"] - row["issued"] > 600
                or row["consumed_by"] is not None and row["consumed_by"] != job_id):
            raise PolicyError("recovery_attestation_missing")
        return row

    def attest(self, target, machine, boot, runbook):
        """Called only by the explicit local root CLI after its three human confirmations."""
        context = self.preview(target, machine, boot, runbook, require_attestation=False)
        digest, now = context["digest"], self.clock()
        evidence = ["independent_access_verified", "recovery_verified", "desktop_maintenance_paused"]
        row = self.db.execute("SELECT consumed_by FROM attestations WHERE digest=?", (digest,)).fetchone()
        if row and row[0] is not None:
            raise PolicyError("job_conflict")
        self.db.execute("INSERT OR REPLACE INTO attestations VALUES (?, ?, ?, ?, ?, NULL)",
                        (digest, json.dumps(context), now, now + 600, json.dumps(evidence)))
        return digest

    def _context(self, plan):
        row = self.db.execute("SELECT context FROM attestations WHERE digest=?", (plan.snapshot.plan_version,)).fetchone()
        if row is None:
            raise PolicyError("recovery_attestation_missing")
        context = json.loads(row["context"])
        if (context["target_id"] != plan.target_id or context["runbook_version"] != plan.snapshot.runbook_version
                or context["packages"] != [asdict(p) for p in plan.snapshot.package_changes]
                or context["boot_id"] != plan.snapshot.boot_id):
            raise PolicyError("plan_changed")
        return context

    def execute(self, plan, job_id):
        if not isinstance(job_id, str) or not HEX32.fullmatch(job_id) or plan.operation != "os_maintenance":
            raise PolicyError("request_invalid")
        context = self._context(plan)
        self._grant(context["digest"])
        self.command(plan.target_id, ["/usr/bin/apt-get", *OPTIONS, "--error-on=any", "update"])
        current = self.preview(plan.target_id, context["machine_id"], context["boot_id"], context["runbook_version"], require_attestation=False)
        if current["digest"] != context["digest"]:
            raise PolicyError("plan_changed")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self._grant(context["digest"])
            self.db.execute("UPDATE attestations SET consumed_by=? WHERE digest=?", (job_id, context["digest"]))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        guard = {key: context[key] for key in ("target_id", "machine_id", "boot_id", "runbook_version",
                                               "apt_configuration_digest", "guard_digest")}
        guard.update(version=1, job_id=job_id, transaction_digest=context["digest"],
                     packages=[[p["name"].split(":")[0], p["candidate"], context["architectures"][p["name"]]]
                               for p in context["packages"]])
        self.command(plan.target_id, ["/usr/bin/python3", "-I", ENTRY_PATH, "maintenance", "prepare-guard", "--job", job_id],
                     json.dumps(guard, separators=(",", ":")).encode())
        pinned = [p["name"] + "=" + p["candidate"] for p in context["packages"]]
        hook = "/usr/bin/python3 -I " + ENTRY_PATH + " maintenance guard --job " + job_id
        self.command(plan.target_id, ["/usr/bin/apt-get", *OPTIONS, "--yes", "-oDpkg::Options::=--force-confold",
                                     "-oDPkg::Pre-Install-Pkgs::=" + hook, "install", *pinned], install=True)

    def verify(self, plan):
        from .remote import decode_wire
        context = self._context(plan)
        state = decode_wire(self.command(plan.target_id, ["/usr/bin/python3", "-I", ENTRY_PATH, "maintenance", "package-state"]))
        if (not isinstance(state, dict) or set(state) != {"version", "idle"}
                or type(state["version"]) is not int or state["version"] != 1 or state["idle"] is not True):
            return False
        if self.command(plan.target_id, ["/usr/bin/dpkg", "--audit"]).strip():
            return False
        output = self.command(plan.target_id, ["/usr/bin/dpkg-query", "--show",
                              "--showformat=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n", "--",
                              *[p["name"] for p in context["packages"]]])
        try:
            actual = [line.split("\t") for line in output.decode("ascii").splitlines()]
        except UnicodeError:
            return False
        expected = [[p["name"].split(":")[0], p["candidate"], context["architectures"][p["name"]], "installed"]
                    for p in context["packages"]]
        if sorted(actual) != sorted(expected):
            return False
        services = self._services(plan.target_id)
        active = {name for name, state in services.items() if state["active"] == "active"}
        return set(context["active_units"]) <= active and set(context["verification_units"]) <= active


def main(argv=None):
    """Root-only local attestation and fixed internal apt helper commands."""
    import argparse
    from .remote import decode_wire
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("identity", "package-state", "prepare-guard", "guard", "attest"))
    parser.add_argument("--job")
    parser.add_argument("--target")
    parser.add_argument("--independent-access-verified", action="store_true")
    parser.add_argument("--recovery-verified", action="store_true")
    parser.add_argument("--desktop-paused", action="store_true")
    args = parser.parse_args(argv)
    resource = None
    try:
        if os.geteuid() != 0:
            raise PolicyError("request_invalid")
        for path in (Path(__file__).absolute(), Path(ENTRY_PATH)):
            if path.resolve() != path:
                raise PolicyError("maintenance_guard_missing")
            for part in (path, *path.parents):
                info = part.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise PolicyError("maintenance_guard_missing")
        confirmations = (args.independent_access_verified, args.recovery_verified, args.desktop_paused)
        if args.action == "attest":
            if not args.target or args.job or not all(confirmations):
                raise PolicyError("request_invalid")
            from .dispatcher import Dispatcher
            resource = Dispatcher.from_file()
            target = resource.registry.resolve(args.target)
            snapshot = resource.prober.snapshot(target, "diagnose", {})
            engine = resource.prober.maintenance()
            digest = engine.attest(target.target_id, resource.config["targets"][target.target_id]["machine_id"],
                                   snapshot.boot_id, resource.config["runbook_version"])
            result = {"version": 1, "transaction_digest": digest, "expires_after_seconds": 600}
        else:
            if args.target or any(confirmations) or args.action in {"identity", "package-state"} and args.job:
                raise PolicyError("request_invalid")
            if args.action == "identity":
                machine, boot = local_identity()
                result = {"version": 1, "machine_id": machine, "boot_id": boot, "guard_digest": helper_digest()}
            elif args.action == "package-state":
                result = {"version": 1, "idle": package_idle()}
            else:
                if not args.job or not HEX32.fullmatch(args.job):
                    raise PolicyError("request_invalid")
                from .dispatcher import read_request
                Path(GUARD_STATE).mkdir(mode=0o700, exist_ok=True)
                resource = GuardJournal()
                payload = read_request(sys.stdin.buffer)
                if args.action == "prepare-guard":
                    resource.prepare(args.job, decode_wire(payload))
                else:
                    resource.verify(args.job, payload)
                result = {"version": 1, "ok": True}
        sys.stdout.buffer.write(json.dumps(result, separators=(",", ":")).encode() + b"\n")
        return 0
    except PolicyError as error:
        sys.stdout.buffer.write(json.dumps({"version": 1, "ok": False, "error_code": error.code}).encode() + b"\n")
        return 1
    except Exception:
        sys.stdout.buffer.write(b'{"version":1,"ok":false,"error_code":"maintenance_unavailable"}\n')
        return 1
    finally:
        if resource is not None:
            resource.close()
