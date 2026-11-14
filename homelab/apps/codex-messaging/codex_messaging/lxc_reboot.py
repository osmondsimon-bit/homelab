"""Reboot reviewed application LXCs gracefully under the authoritative PVE lock."""

from contextlib import contextmanager
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .operations import IDENTIFIER, PROOFS, PolicyError, Snapshot, Target
from .remote import MAX_WIRE, decode_wire

NATIVE_FILES = (
    "/usr/share/perl5/PVE/LXC/Config.pm", "/usr/share/perl5/PVE/AbstractConfig.pm", "/usr/share/perl5/PVE/Tools.pm",
    "/usr/share/perl5/PVE/LXC.pm", "/usr/share/perl5/PVE/LXC/Tools.pm", "/usr/share/perl5/PVE/GuestHelpers.pm",
    "/usr/share/lxc/hooks/lxc-pve-prestart-hook", "/usr/share/lxc/hooks/lxc-pve-poststop-hook",
    "/usr/share/lxc/pve-container-stop-wrapper", "/usr/lib/systemd/system/pve-container@.service",
    "/usr/bin/lxc-info", "/usr/bin/lxc-stop", "/usr/lib/x86_64-linux-gnu/liblxc.so.1",
)
VENDOR_TREES = ("/usr/share/lxc/config", "/usr/share/lxc/hooks", "/usr/share/lxcfs")
HOOKS = ("pre-start", "pre-mount", "mount", "autodev", "start-host", "start", "stop", "post-stop")


def native_inventory():
    paths = set(NATIVE_FILES)
    for directory in VENDOR_TREES:
        root = Path(directory)
        if not root.is_dir() or root.resolve() != root:
            raise PolicyError("guest_verification_unproved")
        for path in root.rglob("*"):
            info = path.lstat()
            if info.st_uid != 0 or not path.is_symlink() and info.st_mode & 0o022:
                raise PolicyError("guest_verification_unproved")
            if path.is_symlink() and path.is_dir():
                raise PolicyError("guest_verification_unproved")
            if path.is_file():
                paths.add(str(path))
            if len(paths) > 1024:
                raise PolicyError("guest_verification_unproved")
    return tuple(sorted(paths))


def native_bytes(path):
    """Read fixed root-protected vendor artifacts; enrollment must review this contract."""
    value = Path(path).resolve()
    original = Path(path)
    allowed = original == value and path in NATIVE_FILES
    if path == "/usr/lib/x86_64-linux-gnu/liblxc.so.1":
        allowed = value.parent == original.parent and re.fullmatch(r"liblxc\.so\.[A-Za-z0-9_.-]+", value.name)
    if any(original.is_relative_to(Path(root)) and value.is_relative_to(Path(root)) for root in VENDOR_TREES):
        allowed = True
    if not allowed:
        raise PolicyError("guest_verification_unproved")
    for part in (value, *value.parents):
        info = part.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise PolicyError("guest_verification_unproved")
    with value.open("rb") as stream:
        result = stream.read(32 * 1024 * 1024 + 1)
    if len(result) > 32 * 1024 * 1024:
        raise PolicyError("guest_verification_unproved")
    return result


@contextmanager
def pve_config_lock(vmid):
    """Match Config.pm config_file_lock and Tools.pm LOCK_EX flock; never unlink it."""
    if type(vmid) is not int or not 100 <= vmid <= 999999999:
        raise PolicyError("identity_unknown")
    directory = descriptor = None
    try:
        directory = os.open("/run/lock/lxc", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise PolicyError("guest_verification_unproved")
        descriptor = os.open("pve-config-" + str(vmid) + ".lock", os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_nlink != 1:
            raise PolicyError("guest_verification_unproved")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise PolicyError("change_busy") from None
    except OSError:
        raise PolicyError("guest_verification_unproved") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if directory is not None:
            os.close(directory)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _properties(payload, keys):
    if not isinstance(payload, bytes) or len(payload) > 65536:
        raise PolicyError("preflight_failed")
    result = {}
    for line in payload.decode("ascii").splitlines():
        name, separator, value = line.partition("=")
        if not separator or name not in keys or name in result:
            raise PolicyError("preflight_failed")
        result[name] = value
    if set(result) != set(keys):
        raise PolicyError("preflight_failed")
    return result


class ApplicationLXCReboot:
    """The trusted identity callback supplies fresh PVE type/location/machine proofs."""

    def __init__(self, config, *, command, reader, identity, health_probe,
                 native_reader=native_bytes, native_inventory=native_inventory, config_lock=pve_config_lock):
        self.config, self.command, self.reader, self.identity = config, command, reader, identity
        self.health_probe, self.native_reader, self.config_lock = health_probe, native_reader, config_lock
        self.native_inventory = native_inventory

    def _policy(self, target):
        policy = self.config.get("reboot_policies", {}).get(target.target_id)
        registered = self.config["targets"].get(target.target_id)
        expected = {"role", "control_dependencies", "required_units", "shutdown_timeout", "native_contract_digest"}
        if (target.kind != "lxc" or not isinstance(registered, dict) or registered.get("kind") != "lxc"
                or type(registered.get("vmid")) is not int or not 100 <= registered["vmid"] <= 999999999
                or target.target_id == self.config["management_target_id"]
                or not isinstance(policy, dict) or set(policy) != expected or policy["role"] != "application"
                or policy["control_dependencies"] != [] or not isinstance(policy["required_units"], list)
                or not 1 <= len(policy["required_units"]) <= 16 or len(set(policy["required_units"])) != len(policy["required_units"])
                or not set(policy["required_units"]) <= set(registered["units"])
                or type(policy["shutdown_timeout"]) is not int or not 10 <= policy["shutdown_timeout"] <= 120
                or not isinstance(policy["native_contract_digest"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", policy["native_contract_digest"])):
            raise PolicyError("guest_verification_unproved")
        health = self.config["service_policies"].get(target.target_id, {})
        if not set(policy["required_units"]) <= set(health):
            raise PolicyError("guest_verification_unproved")
        return policy

    def _api(self, path):
        return decode_wire(self.command(["/usr/bin/pvesh", "get", path, "--output-format", "json"], timeout=15, limit=MAX_WIRE))

    def _guest_boot(self, vmid, parent):
        output = self.command(["/usr/bin/lxc-info", "-n", str(vmid), "-p", "-H"], timeout=5, limit=128).decode().strip()
        if not re.fullmatch(r"[0-9]{1,10}", output) or not 1 < int(output) < 2 ** 31:
            raise PolicyError("identity_unknown")
        data = self.reader("/proc/" + output + "/stat")
        if not isinstance(data, str) or len(data) > 8192:
            raise PolicyError("identity_unknown")
        opening, closing = data.find("("), data.rfind(")")
        fields = data[closing + 1:].split()
        if (opening < 0 or closing < opening or data[:opening].strip() != output or len(fields) < 20
                or fields[0] not in {"R", "S", "I"} or not fields[19].isdigit() or int(fields[19]) <= 0):
            raise PolicyError("identity_unknown")
        again = self.command(["/usr/bin/lxc-info", "-n", str(vmid), "-p", "-H"], timeout=5, limit=128).decode().strip()
        if again != output:
            raise PolicyError("identity_changed")
        return _hash([parent, output, fields[19]])

    def _snapshot(self, target, *, approved_boot=None):
        policy = self._policy(target)
        management_host, _guest_kernel_boot = self.identity(target)
        parent = self.reader("/proc/sys/kernel/random/boot_id").strip()
        if not IDENTIFIER.fullmatch(parent):
            raise PolicyError("identity_unknown")
        native = {path: hashlib.sha256(self.native_reader(path)).hexdigest() for path in self.native_inventory()}
        contract = _hash(native)
        if contract != policy["native_contract_digest"]:
            raise PolicyError("guest_verification_unproved")
        vmid = self.config["targets"][target.target_id]["vmid"]
        node = self.config["targets"][self.config["local_target_id"]]["pve_node"]
        path = "/nodes/" + node + "/lxc/" + str(vmid)
        status, current, pending = self._api(path + "/status/current"), self._api(path + "/config"), self._api(path + "/pending")
        if (not isinstance(status, dict) or status.get("vmid") != vmid or status.get("status") != "running"
                or not isinstance(status.get("ha"), dict) or status["ha"].get("managed") not in (0, False)
                or not isinstance(current, dict) or current.get("onboot") not in (1, True)
                or current.get("lock") not in (None, "") or current.get("hookscript") not in (None, "")
                or current.get("template", 0) not in (0, False) or current.get("debug", 0) not in (0, False)
                or current.get("lxc", []) != [] or not isinstance(current.get("digest"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", current["digest"]) or not isinstance(pending, list)
                or any(not isinstance(item, dict) or not {"key"} <= set(item)
                       or not set(item) <= {"key", "value", "pending", "delete"}
                       or "pending" in item or item.get("delete", 0) not in (0, False) for item in pending)):
            raise PolicyError("preflight_failed")
        ha, cluster = self._api("/cluster/ha/resources"), self._api("/cluster/status")
        if (not isinstance(ha, list) or any(not isinstance(item, dict) or not isinstance(item.get("sid"), str) for item in ha)
                or any(item["sid"] in {"ct:" + str(vmid), "vm:" + str(vmid)} for item in ha)
                or not isinstance(cluster, list) or len([item for item in cluster if isinstance(item, dict)
                    and item.get("type") == "cluster" and item.get("quorate") in (1, True)]) != 1):
            raise PolicyError("preflight_failed")
        unit = _properties(self.command(["/usr/bin/systemctl", "show", "pve-container@" + str(vmid) + ".service",
                                         "--property=FragmentPath,DropInPaths", "--all", "--no-pager"], timeout=10, limit=4096),
                           {"FragmentPath", "DropInPaths"})
        if unit["FragmentPath"] not in {"/usr/lib/systemd/system/pve-container@.service", "/lib/systemd/system/pve-container@.service"} or unit["DropInPaths"]:
            raise PolicyError("guest_verification_unproved")
        signal = self.command(["/usr/bin/lxc-info", "-n", str(vmid), "-c", "lxc.signal.reboot", "-H"], timeout=5, limit=128).decode().strip()
        if signal not in {"", "SIGINT", "2"}:
            raise PolicyError("guest_verification_unproved")
        for hook in HOOKS:
            configured = self.command(["/usr/bin/lxc-info", "-n", str(vmid), "-c", "lxc.hook." + hook, "-H"], timeout=5, limit=4096).decode().strip()
            if any(path not in native for path in configured.splitlines()):
                raise PolicyError("guest_verification_unproved")
        health = self.config["service_policies"][target.target_id]
        for required in policy["required_units"]:
            state = _properties(self.command(["/usr/sbin/pct", "exec", str(vmid), "--", "/usr/bin/systemctl", "show", required,
                                              "--property=ActiveState,UnitFileState", "--no-pager"], timeout=15, limit=4096),
                                {"ActiveState", "UnitFileState"})
            if state != {"ActiveState": "active", "UnitFileState": "enabled"} or self.health_probe(health[required]["health_url"]) is not True:
                raise PolicyError("health_unverified")
        boot = self._guest_boot(vmid, parent)
        if self.reader("/proc/sys/kernel/random/boot_id").strip() != parent:
            raise PolicyError("identity_changed")
        version = _hash([current, pending, policy, {unit: health[unit] for unit in policy["required_units"]},
                         contract, parent, approved_boot or boot])
        return Snapshot(target.target_id, target.kind, self.config["management_target_id"], management_host,
                        self.config["runbook_version"], version, True, affected_target_ids=(target.target_id,),
                        impact=("The application guest and all of its services will be unavailable during its graceful reboot.",),
                        verification=("New container init process instance on the unchanged parent boot", "Registered application health and enabled required units"),
                        preconditions=tuple(sorted(PROOFS["guest_reboot"])), boot_id=boot, parent_boot_id=parent)

    def snapshot(self, target):
        self._policy(target)
        with self.config_lock(self.config["targets"][target.target_id]["vmid"]):
            return self._snapshot(target)

    def execute(self, plan):
        if plan.operation != "guest_reboot" or plan.parameters:
            raise PolicyError("operation_unsupported")
        target = Target(plan.target_id, plan.target_kind)
        policy = self._policy(target)
        vmid = self.config["targets"][target.target_id]["vmid"]
        with self.config_lock(vmid):
            if self._snapshot(target) != plan.snapshot:
                raise PolicyError("plan_changed")
            self.command(["/usr/bin/lxc-stop", "-n", str(vmid), "--reboot", "--nokill", "--timeout", str(policy["shutdown_timeout"])],
                         timeout=policy["shutdown_timeout"] + 15, limit=65536)

    def verify(self, plan):
        if plan.operation != "guest_reboot" or plan.parameters:
            return False, None
        target = Target(plan.target_id, plan.target_kind)
        try:
            with self.config_lock(self.config["targets"][target.target_id]["vmid"]):
                current = self._snapshot(target, approved_boot=plan.snapshot.boot_id)
                unchanged = replace(current, boot_id=plan.snapshot.boot_id) == plan.snapshot
                return unchanged and current.boot_id != plan.snapshot.boot_id, current.boot_id
        except Exception:
            return False, None
