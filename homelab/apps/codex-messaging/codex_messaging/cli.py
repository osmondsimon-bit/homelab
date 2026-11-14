"""Pair one Telegram owner and run a thin relay using the existing Codex user."""

import argparse
import asyncio
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time

from .normal_worker import NormalWorker
from .relay import Relay
from .transport import Telegram, TransportRejected

RUNTIMES = {
    "codex_binary": "b452ca20f838a8855a88a41050ee4a694033fff4ea3ecdad5633e6e0e8d13f2b",
    "bwrap_binary": "711ac2c00998eede367c2b3827efa36ba4436dfce19ab9d3b6d56ff5a5996fa1",
}


class ConfigurationRejected(Exception):
    """Keep local errors free of file contents, credentials and request URLs."""


def private_read(path, maximum=8192):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > maximum):
            raise ConfigurationRejected("private_file_permissions")
        return os.read(descriptor, maximum + 1).decode()
    finally:
        os.close(descriptor)


def settings(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_size > 8192:
            raise ConfigurationRejected("configuration_permissions")
        result = json.loads(os.read(descriptor, 8193))
    finally:
        os.close(descriptor)
    expected = {"user_home", "workspace", "state_dir", *RUNTIMES}
    if not isinstance(result, dict) or set(result) != expected or any(
            not isinstance(value, str) or not Path(value).is_absolute() for value in result.values()):
        raise ConfigurationRejected("configuration_shape")
    result = {key: Path(value) for key, value in result.items()}
    for key in ("user_home", "workspace", "state_dir"):
        if not result[key].is_dir():
            raise ConfigurationRejected("configuration_directory")
    state = result["state_dir"].lstat()
    if not stat.S_ISDIR(state.st_mode) or state.st_uid != os.getuid() or state.st_mode & 0o077:
        raise ConfigurationRejected("private_state_permissions")
    if result["codex_binary"].parent != result["bwrap_binary"].parent:
        raise ConfigurationRejected("runtime_directory")
    return result


def check_runtime(config):
    for key, digest in RUNTIMES.items():
        path = config[key]
        for parent in path.parents:
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ConfigurationRejected("runtime_directory_permissions")
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ConfigurationRejected("runtime_file_permissions")
        with path.open("rb") as binary:
            info = os.fstat(binary.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o7022
                    or not info.st_mode & 0o111 or hashlib.file_digest(binary, "sha256").hexdigest() != digest):
                raise ConfigurationRejected("runtime_integrity")


@contextlib.contextmanager
def state_lock(directory):
    descriptor = os.open(directory / "relay.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ConfigurationRejected("private_lock_permissions")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


async def pair(client, destination, *, announce=print, clock=time.time):
    if destination.exists():
        raise ConfigurationRejected("already_paired")
    nonce, started = secrets.token_urlsafe(24), clock()
    phrase = "/pair " + nonce
    announce("Send " + phrase + " in a private chat with your bot within ten minutes.")
    offset = 0
    while clock() - started < 600:
        updates = await asyncio.to_thread(client.get_updates, offset)
        for update in updates:
            identifier, message = update.get("update_id"), update.get("message", {})
            if type(identifier) is not int or identifier < offset:
                continue
            offset = identifier + 1
            if not isinstance(message, dict):
                continue
            sender, chat, stamp = message.get("from", {}), message.get("chat", {}), message.get("date")
            if (not isinstance(sender, dict) or not isinstance(chat, dict)
                    or message.get("text") != phrase or chat.get("type") != "private"
                    or sender.get("is_bot") is not False or type(sender.get("id")) is not int
                    or type(chat.get("id")) is not int or sender["id"] <= 0 or chat["id"] != sender["id"]
                    or type(stamp) is not int or not started - 5 <= stamp <= clock() + 60):
                continue
            descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w") as output:
                json.dump({"user_id": sender["id"], "chat_id": chat["id"], "offset": offset, "paired_at": int(clock())}, output)
                output.flush()
                os.fsync(output.fileno())
            announce("Paired. Only this private Telegram account can use the relay.")
            return
    raise ConfigurationRejected("pairing_expired")


async def serve(config, client, owner):
    environment = dict(os.environ)
    environment["PATH"] = str(config["bwrap_binary"].parent) + os.pathsep + environment.get("PATH", os.defpath)
    async with NormalWorker([str(config["codex_binary"])], config["user_home"], config["workspace"], inherited=environment) as worker:
        relay = Relay(config["state_dir"] / "relay.sqlite", owner["user_id"], owner["chat_id"], worker,
                      home=config["user_home"], offset=owner["offset"])
        polling = asyncio.create_task(asyncio.to_thread(client.get_updates, relay.cursor()))
        event = asyncio.create_task(worker.next_event())
        sending = None
        retry_at = 0
        try:
            while True:
                pending = {polling, event}
                if sending:
                    pending.add(sending[1])
                done, _ = await asyncio.wait(pending, timeout=1, return_when=asyncio.FIRST_COMPLETED)
                if event.done():
                    await relay.event(event.result())
                    event = asyncio.create_task(worker.next_event())
                await relay.tick()
                if polling in done:
                    try:
                        updates = polling.result()
                    except TransportRejected:
                        updates = []
                        await asyncio.sleep(5)
                    for update in updates:
                        await relay.handle(update)
                    polling = asyncio.create_task(asyncio.to_thread(client.get_updates, relay.cursor()))
                if sending and sending[1] in done:
                    try:
                        sending[1].result()
                        relay.sent(sending[0])
                    except TransportRejected:
                        retry_at = time.monotonic() + 5
                    sending = None
                if sending is None and time.monotonic() >= retry_at:
                    messages = relay.outbox()
                    if messages:
                        identifier, body = messages[0]
                        sending = (identifier, asyncio.create_task(asyncio.to_thread(client.send_message, body)))
        finally:
            for task in [polling, event, sending[1] if sending else None]:
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
            relay.close()


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Pair and run a private Telegram-to-Codex relay.")
    parser.add_argument("--config", type=Path, default=Path("/etc/codex-telegram.json"))
    parser.add_argument("command", choices=("check", "pair", "serve"))
    options = parser.parse_args(arguments)
    os.umask(0o077)
    try:
        config = settings(options.config)
        check_runtime(config)
        if options.command == "check":
            print("Configuration and pinned runtime hashes verified. Subscription, native sandbox and Telegram still need the target-VM smoke checks.")
            return 0
        with state_lock(config["state_dir"]):
            client = Telegram(private_read(config["state_dir"] / "bot-token").strip())
            enrollment = config["state_dir"] / "enrollment.json"
            if options.command == "pair":
                asyncio.run(pair(client, enrollment))
            else:
                owner = json.loads(private_read(enrollment))
                if (not isinstance(owner, dict) or set(owner) != {"user_id", "chat_id", "offset", "paired_at"}
                        or any(type(value) is not int or value < 0 for value in owner.values())
                        or not owner["user_id"] or owner["chat_id"] != owner["user_id"]):
                    raise ConfigurationRejected("enrollment_shape")
                asyncio.run(serve(config, client, owner))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        category = str(error) if isinstance(error, ConfigurationRejected) else getattr(error, "code", None)
        if not isinstance(category, str) or not re.fullmatch(r"[a-z_]{1,60}", category):
            category = "local_check_failed"
        print(f"Relay stopped ({category}): check locally. Private details were not logged.", file=sys.stderr)
        return 1
