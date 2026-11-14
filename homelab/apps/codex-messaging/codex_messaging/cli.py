"""Run the keyless commissioning stage with fixed paths and separately owned roles."""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile
import time

from .authentication import AuthenticationRejected, worker_environment
from .configuration import ConfigurationRejected, keyless_settings
from .gateway import Coordinator
from .ipc import BrokerSocketServer
from .operations import OperationsBroker, PolicyError, TargetRegistry
from .preflight import RuntimeRejected, inspect_runtime
from .remote import decode_wire, protected_json, run_bounded
from .rpc import RpcWorker, WorkerRejected
from .transport import BrokerClient, Telegram, TransportRejected
from .worker_policy import verify_features


CODE = Path("/opt/codex-messaging")
STATE = Path("/var/lib/codex-messaging")
WORKER_HOME = STATE / "worker"
REFERENCE = STATE / "reference"
SOCKET = Path("/run/codex-messaging/broker/operations.sock")


def _role(name):
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        raise ConfigurationRejected("service_role") from None
    if os.geteuid() != account.pw_uid:
        raise ConfigurationRejected("service_role")
    return account


def _clean_environment(home):
    selected = worker_environment(home, os.environ)
    selected.pop("CODEX_HOME")
    os.environ.clear()
    os.environ.update(selected)


def _private(path, owner, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o077 or info.st_size > limit:
            raise ConfigurationRejected("private_file_permissions")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(limit + 1)
    finally:
        os.close(descriptor)


def _root_hash(path, worker_group):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ConfigurationRejected("runtime_permissions")
        for parent in path.parents:
            info = parent.stat()
            permitted_sticky = (parent in {WORKER_HOME, WORKER_HOME / ".codex"}
                                and info.st_uid == 0 and info.st_gid == worker_group
                                and stat.S_IMODE(info.st_mode) == 0o1770)
            if info.st_uid != 0 or info.st_mode & 0o022 and not permitted_sticky:
                raise ConfigurationRejected("runtime_permissions")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    finally:
        os.close(descriptor)


def _worker(login=False):
    account = _role("codex-worker")
    manifest = protected_json("/etc/codex-messaging/worker.json")
    fields = {"version", "binary_sha256", "bwrap_sha256", "config_sha256"}
    if set(manifest) != fields or manifest["version"] != 1 or any(
            not isinstance(manifest[field], str) or not re.fullmatch(r"[0-9a-f]{64}", manifest[field])
            for field in fields - {"version"}):
        raise ConfigurationRejected("runtime_manifest")
    binary = CODE / "runtime/bin/codex"
    for path, field in [(binary, "binary_sha256"),
                        (CODE / "runtime/codex-resources/bwrap", "bwrap_sha256"),
                        (WORKER_HOME / ".codex/config.toml", "config_sha256")]:
        if _root_hash(path, account.pw_gid) != manifest[field]:
            raise ConfigurationRejected("runtime_digest")
    environment = worker_environment(WORKER_HOME, os.environ)
    version = run_bounded([str(binary), "--version"], environment=environment, limit=4096, timeout=15)
    if version.decode().strip() != "codex-cli 0.146.0":
        raise ConfigurationRejected("runtime_version")
    feature_table = run_bounded([str(binary), "features", "list"],
                                environment=environment, limit=16384, timeout=20)
    try:
        verify_features(feature_table.decode())
    except (ValueError, UnicodeError):
        raise ConfigurationRejected("worker_features") from None
    os.chdir(REFERENCE)
    arguments = [str(binary)]
    arguments += ["login", "--device-auth"] if login else ["--strict-config", "app-server", "--listen", "stdio://"]
    os.execve(binary, arguments, environment)


class _NoRemoteAuthority:
    def inspect(self, *_args, **_kwargs):
        raise PolicyError("not_enrolled")

    def dispatch(self, *_args, **_kwargs):
        raise PolicyError("not_enrolled")

    def query(self, *_args, **_kwargs):
        raise PolicyError("not_enrolled")


def _broker():
    account = _role("codex-ops")
    _clean_environment(STATE / "operations")
    settings = keyless_settings(protected_json("/etc/codex-messaging/broker.json"))
    operations = OperationsBroker(STATE / "operations/jobs.sqlite", TargetRegistry([]), _NoRemoteAuthority())
    operations.pause()
    peer = pwd.getpwnam("codex-telegram").pw_uid
    server = BrokerSocketServer(SOCKET, operations, allowed_uid=peer, user_id=settings["user_id"],
                                chat_id=settings["chat_id"], allow_changes=False)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        operations.close()


def _health(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".health-", delete=False) as output:
        temporary = Path(output.name)
        os.fchmod(output.fileno(), 0o600)
        output.write(json.dumps(value).encode())
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


async def _gateway():
    account = _role("codex-telegram")
    _clean_environment(STATE / "telegram")
    settings = keyless_settings(protected_json("/etc/codex-messaging/gateway.json"))
    token = _private(STATE / "telegram/bot-token", account.pw_uid, 256).decode().strip()
    telegram = Telegram(token)
    broker = BrokerClient(str(SOCKET))
    launcher = ["/usr/bin/sudo", "-n", "-u", "codex-worker", "--", "/usr/local/libexec/codex-messaging-worker"]
    async with RpcWorker(launcher, WORKER_HOME, REFERENCE) as worker:
        gateway = Coordinator(STATE / "telegram/gateway.sqlite", settings["user_id"], settings["chat_id"], worker, broker)
        await gateway.startup()
        poll = asyncio.create_task(asyncio.to_thread(telegram.get_updates, gateway.cursor()))
        event = asyncio.create_task(worker.next_event())
        poll_healthy, last_health = False, 0
        try:
            while True:
                done, _ = await asyncio.wait({poll, event}, timeout=1, return_when=asyncio.FIRST_COMPLETED)
                if poll in done:
                    try:
                        updates = poll.result()
                        poll_healthy = True
                        for update in updates:
                            try:
                                await gateway.handle(update)
                            except (PolicyError, WorkerRejected, ConnectionError, OSError, TimeoutError):
                                await broker.pause()
                                with gateway.database:
                                    gateway._set("paused", True)
                                    gateway._reply("Request needs local review. No uncertain operation will be replayed.")
                    except TransportRejected as error:
                        poll_healthy = False
                        await asyncio.sleep(min(error.retry_after, 30))
                    poll = asyncio.create_task(asyncio.to_thread(telegram.get_updates, gateway.cursor()))
                if event in done:
                    await gateway.worker_event(event.result())
                    event = asyncio.create_task(worker.next_event())
                await gateway.tick()
                await gateway.maintain()
                for identifier, body in gateway.outbox():
                    try:
                        await asyncio.to_thread(telegram.send_message, body)
                    except TransportRejected:
                        poll_healthy = False
                        break
                    gateway.sent(identifier)
                if time.time() - last_health >= 30:
                    _health(STATE / "telegram/health.json", {"updated": time.time(), "worker_alive": 1,
                            "poll_healthy": int(poll_healthy), "paused": 1, "outbox_pending": len(gateway.outbox())})
                    last_health = time.time()
        finally:
            poll.cancel()
            event.cancel()
            for task in (poll, event):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            gateway.close()


def _metrics():
    if os.geteuid() != 0:
        raise ConfigurationRejected("service_role")
    account = pwd.getpwnam("codex-telegram")
    healthy, stamp, worker, poll, pending = 0, 0, 0, 0, 0
    try:
        health = decode_wire(_private(STATE / "telegram/health.json", account.pw_uid, 2048))
        if set(health) != {"updated", "worker_alive", "poll_healthy", "paused", "outbox_pending"}:
            raise ValueError("health")
        if (type(health["updated"]) not in {int, float} or not 0 <= time.time() - health["updated"] <= 180
                or any(type(health[name]) is not int or health[name] not in {0, 1} for name in ("worker_alive", "poll_healthy", "paused"))
                or type(health["outbox_pending"]) is not int or not 0 <= health["outbox_pending"] <= 10000):
            raise ValueError("health")
        stamp, worker, poll, pending = health["updated"], health["worker_alive"], health["poll_healthy"], health["outbox_pending"]
        healthy = int(worker == 1 and poll == 1)
    except (OSError, ValueError, PolicyError, ConfigurationRejected):
        pass
    body = (f"codex_messaging_healthy {healthy}\ncodex_messaging_last_heartbeat_timestamp_seconds {stamp}\n"
            f"codex_messaging_worker_alive {worker}\ncodex_messaging_poll_healthy {poll}\n"
            f"codex_messaging_outbox_pending {pending}\ncodex_messaging_changes_enabled 0\n")
    directory = Path("/var/lib/prometheus/node-exporter")
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".codex-messaging-", delete=False) as output:
        temporary = Path(output.name)
        output.write(body.encode())
        os.fchmod(output.fileno(), 0o644)
    os.replace(temporary, directory / "codex_messaging.prom")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Codex messaging keyless commissioning stage")
    parser.add_argument("command", choices=["gateway", "broker", "worker", "worker-login", "metrics", "preflight", "dispatcher", "maintenance"])
    arguments, remaining = parser.parse_known_args(argv)
    try:
        if arguments.command in {"dispatcher", "maintenance"}:
            if os.geteuid() != 0:
                raise ConfigurationRejected("service_role")
            if arguments.command == "dispatcher":
                from .dispatcher import main as dispatch
            else:
                from .maintenance import main as dispatch
            return dispatch(remaining)
        if arguments.command == "preflight":
            probe = argparse.ArgumentParser(description="Keyless pinned-runtime validation")
            probe.add_argument("--binary", type=Path, required=True)
            selected = probe.parse_args(remaining)
            metadata = inspect_runtime(selected.binary)
            sys.path.insert(0, str(CODE / "tests" if CODE.exists() else Path(__file__).resolve().parents[1] / "tests"))
            from runtime_fixture import run_fixture
            evidence = run_fixture(selected.binary, native_environment=False)
            allowed = {"fixture_diagnostic", "request_user_input", "skills.list", "skills.read", "update_plan"}
            if (any(evidence[name] != "unavailable" for name in ("native_shell", "native_image", "native_agent"))
                    or evidence["dynamic_tool"] != "completed" or not set(evidence["advertised_tools"]) <= allowed
                    or any(json.loads(evidence[name]).get("skills") != [] for name in ("skills_listing", "executor_skills_listing"))
                    or any(evidence[name] != "skill package is not available from the requested authority" for name in ("orchestrator_read", "executor_read"))):
                raise RuntimeRejected("worker_isolation")
            print(json.dumps({**metadata, "dynamic_only_gate": "passed", "live_account_gate": "pending"}))
            return 0
        if remaining:
            raise ConfigurationRejected("command_arguments")
        if arguments.command in {"worker", "worker-login"}:
            _worker(login=arguments.command == "worker-login")
        elif arguments.command == "broker":
            _broker()
        elif arguments.command == "metrics":
            _metrics()
        else:
            asyncio.run(_gateway())
        return 0
    except (ConfigurationRejected, PolicyError, RuntimeRejected, AuthenticationRejected, WorkerRejected, TransportRejected) as error:
        print(error.code, file=sys.stderr)
        return 1
    except Exception:
        print("service_unavailable", file=sys.stderr)
        return 1
