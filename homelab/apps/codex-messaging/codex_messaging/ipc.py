"""Serve the typed broker protocol only to the coordinator's OS and chat identity."""

from dataclasses import asdict, is_dataclass
import json
import os
import socket
import socketserver
import stat
import struct

from .operations import PolicyError


def _serial(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (tuple, list)):
        return [_serial(item) for item in value]
    return value


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(15)
        try:
            _, peer_uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if peer_uid != self.server.allowed_uid:
                raise PolicyError("peer_not_allowed")
            line = self.rfile.readline(128_001)
            if len(line) > 128_000 or not line.endswith(b"\n"):
                raise PolicyError("request_invalid")
            request = json.loads(line)
            if not isinstance(request, dict) or set(request) != {"version", "method", "arguments"} or request["version"] != 1:
                raise PolicyError("request_invalid")
            method, arguments = request["method"], request["arguments"]
            schemas = {
                "prepare": {"user_id", "chat_id", "target_alias", "operation", "parameters"},
                "approve": {"user_id", "chat_id", "approval_id", "plan_digest"},
                "diagnose": {"user_id", "chat_id", "target_alias", "parameters"},
                "pause": set(), "resume": set(), "stop": set(), "recoverable_jobs": set(),
                "status": {"job_id"}, "reconcile": {"job_id"},
            }
            if not isinstance(method, str) or method not in schemas or not isinstance(arguments, dict) or set(arguments) != schemas[method]:
                raise PolicyError("request_invalid")
            if "user_id" in arguments and (type(arguments["user_id"]) is not int or type(arguments["chat_id"]) is not int
                    or (arguments["user_id"], arguments["chat_id"]) != (self.server.user_id, self.server.chat_id)):
                raise PolicyError("identity_not_allowed")
            if method in {"resume", "prepare", "approve"} and not self.server.allow_changes:
                raise PolicyError("not_enrolled")
            result = getattr(self.server.operations, method)(**arguments)
            response = _serial(result)
            if method in {"diagnose", "status", "reconcile"} and result.operation == "diagnose":
                response["diagnostics"] = self.server.operations.diagnostic_result(result.job_id)
            reply = {"ok": True, "result": response}
        except PolicyError as error:
            reply = {"ok": False, "error": error.code}
        except Exception:
            reply = {"ok": False, "error": "broker_unavailable"}
        with self.request.makefile("wb") as output:
            output.write(json.dumps(reply).encode() + b"\n")
            output.flush()


class BrokerSocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """The production caller fixes the socket, principal and grants from protected config."""

    daemon_threads = True

    def __init__(self, path, operations, *, allowed_uid, user_id, chat_id, allow_changes=False):
        if any(type(value) is not int or value < 0 for value in (allowed_uid, user_id, chat_id)) or min(user_id, chat_id) == 0:
            raise PolicyError("configuration_invalid")
        parent = path.parent.stat()
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
            raise PolicyError("socket_permissions")
        if os.path.lexists(path):
            info = path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
                raise PolicyError("socket_permissions")
            path.unlink()
        self.allowed_uid, self.user_id, self.chat_id = allowed_uid, user_id, chat_id
        self.operations = operations
        self.allow_changes = allow_changes is True
        super().__init__(str(path), _Handler)
        os.chmod(path, 0o660)
