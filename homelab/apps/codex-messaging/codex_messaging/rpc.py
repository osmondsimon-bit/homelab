"""Keep the coordinator's worker RPC surface local, bounded and subscription-only."""

import asyncio
import contextlib
import json
import os
import uuid
from pathlib import Path

from .authentication import AuthenticationRejected, require_subscription, worker_environment
from .worker_policy import thread_parameters


TOOLS = [
    {"type": "function", "name": "diagnose", "description": "Run a registered read-only probe against a logical target.",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"},
                     "probe": {"enum": ["health", "resources", "packages", "reboot", "dns", "unit_logs"]},
                     "unit": {"type": "string"}}, "required": ["target"], "additionalProperties": False}},
    {"type": "function", "name": "propose_operation", "description": "Prepare a reviewed change for a separate single-use human approval. This tool cannot authorise it.",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"},
                     "operation": {"enum": ["service_restart", "guest_reboot", "host_reboot", "os_maintenance"]},
                     "unit": {"type": "string"}}, "required": ["target", "operation"], "additionalProperties": False}},
]


class WorkerRejected(Exception):
    """Describe worker failures without echoing server messages or tool output."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class RpcWorker:
    """Talk only to a fixed local launcher; chat/model text never becomes RPC methods."""

    METHODS = frozenset({"initialize", "account/read", "account/rateLimits/read", "thread/start",
                         "thread/resume", "thread/list", "thread/delete", "turn/start", "turn/interrupt"})

    def __init__(self, launcher, context: Path, workspace: Path, *, inherited=None):
        self.launcher = tuple(launcher)
        self.context, self.workspace = context, workspace
        self.environment = worker_environment(context, os.environ if inherited is None else inherited)
        self.process = None
        self.reader = None
        self.pending = {}
        self.events = asyncio.Queue(maxsize=256)
        self.sequence = 0
        self.active = None
        self.tool_requests = {}
        self.failed = False

    async def __aenter__(self):
        self.process = await asyncio.create_subprocess_exec(
            *self.launcher, cwd=self.workspace, env=self.environment,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=1_000_000,
        )
        self.reader = asyncio.create_task(self._read())
        try:
            await self._request("initialize", {"clientInfo": {"name": "homelab-messaging", "version": "1"},
                                               "capabilities": {"experimentalApi": True}})
            await self._send({"method": "initialized"})
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *_args):
        if self.process and self.process.stdin:
            self.process.stdin.close()
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        self.process.kill()
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.reader

    async def _send(self, value):
        if not self.process or self.process.returncode is not None:
            raise WorkerRejected("worker_unavailable")
        self.process.stdin.write(json.dumps(value).encode() + b"\n")
        await self.process.stdin.drain()

    async def _request(self, method, parameters):
        if method not in self.METHODS:
            raise WorkerRejected("rpc_not_allowed")
        self.sequence += 1
        identifier = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            await self._send({"id": identifier, "method": method, "params": parameters})
            return await asyncio.wait_for(future, timeout=30)
        except (TimeoutError, BrokenPipeError, ConnectionError):
            raise WorkerRejected("worker_unavailable") from None
        finally:
            self.pending.pop(identifier, None)

    async def _read(self):
        try:
            while line := await self.process.stdout.readline():
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("envelope")
                identifier = message.get("id")
                if "method" not in message and type(identifier) is int and identifier in self.pending:
                    future = self.pending[identifier]
                    if not future.done():
                        if "error" in message:
                            future.set_exception(WorkerRejected("worker_rpc_rejected"))
                        else:
                            future.set_result(message.get("result", {}))
                elif "method" in message:
                    self.events.put_nowait(message)
        except (ValueError, asyncio.QueueFull, OSError):
            pass
        finally:
            self.failed = True
            with contextlib.suppress(asyncio.QueueFull):
                self.events.put_nowait({"method": "worker/failed"})
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(WorkerRejected("worker_unavailable"))

    async def prune_inactive(self, before):
        """Delete only old inactive threads from this dedicated context and workspace."""
        candidates = set()
        for archived in (False, True):
            cursor, seen = None, set()
            for _page in range(100):
                reply = await self._request("thread/list", {"cwd": str(self.workspace), "limit": 100,
                    "archived": archived, "modelProviders": [], "cursor": cursor, "useStateDbOnly": True})
                if not isinstance(reply, dict) or not isinstance(reply.get("data"), list):
                    raise WorkerRejected("retention_metadata")
                for thread in reply["data"]:
                    if not isinstance(thread, dict):
                        raise WorkerRejected("retention_metadata")
                    if (thread.get("cwd") != str(self.workspace)
                            or not isinstance(thread.get("status"), dict)
                            or thread["status"].get("type") not in {"idle", "notLoaded"}
                            or type(thread.get("updatedAt")) not in {int, float}
                            or not 0 <= thread["updatedAt"] < before):
                        continue
                    identifier = thread.get("id")
                    try:
                        if str(uuid.UUID(identifier)) != identifier:
                            raise ValueError("thread")
                    except (ValueError, TypeError, AttributeError):
                        raise WorkerRejected("retention_metadata") from None
                    candidates.add(identifier)
                cursor = reply.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or cursor in seen:
                    raise WorkerRejected("retention_metadata")
                seen.add(cursor)
            else:
                raise WorkerRejected("retention_metadata")
        for identifier in sorted(candidates):
            await self._request("thread/delete", {"threadId": identifier})
        return len(candidates)

    async def begin(self, text, thread_id=None):
        account = await self._request("account/read", {"refreshToken": False})
        if not isinstance(account.get("account"), dict) or account["account"].get("type") != "chatgpt":
            raise AuthenticationRejected("subscription_required")
        limits = await self._request("account/rateLimits/read", {})
        require_subscription(account, limits)
        parameters = thread_parameters(str(self.workspace), TOOLS)
        if thread_id:
            parameters.pop("dynamicTools")
            parameters["threadId"] = thread_id
            thread = await self._request("thread/resume", parameters)
        else:
            parameters["allowProviderModelFallback"] = False
            parameters["developerInstructions"] = (
                "Investigate through diagnose. Propose changes only through propose_operation; "
                "human approval occurs outside the model. Never claim an action completed from a "
                "request acknowledgement. Use logical target names. Do not include addresses, "
                "credentials, raw logs or files in your final summary. Unfamiliar repairs need "
                "desktop review. Ask concise follow-up questions when target or intent is unclear."
            )
            thread = await self._request("thread/start", parameters)
        identifier = thread.get("thread", {}).get("id")
        if not isinstance(identifier, str):
            raise WorkerRejected("worker_protocol")
        turn = await self._request("turn/start", {"threadId": identifier,
            "input": [{"type": "text", "text": text}], "permissions": "messaging", "environments": [],
            "serviceTier": "default", "outputSchema": {"type": "object", "properties": {"summary": {"type": "string", "maxLength": 1600}},
                                                       "required": ["summary"], "additionalProperties": False}})
        turn_id = turn.get("turn", {}).get("id")
        if not isinstance(turn_id, str):
            raise WorkerRejected("worker_protocol")
        self.active = (identifier, turn_id)
        return self.active

    async def next_event(self):
        if self.failed:
            raise WorkerRejected("worker_unavailable")
        event = await self.events.get()
        if self.failed:
            raise WorkerRejected("worker_unavailable")
        if "id" in event:
            parameters = event.get("params", {})
            if (event.get("method") not in {"item/tool/call", "item/tool/requestUserInput"}
                    or not self.active or (parameters.get("threadId"), parameters.get("turnId")) != self.active):
                await self._send({"id": event["id"], "error": {"code": -32601, "message": "request not supported"}})
                await self.interrupt()
                raise WorkerRejected("worker_request_not_allowed")
            self.tool_requests[event["id"]] = event
        if (event.get("method") == "turn/completed"
                and (event.get("params", {}).get("threadId"), event.get("params", {}).get("turn", {}).get("id")) == self.active):
            self.active = None
            self.tool_requests.clear()
        return event

    async def tool_result(self, event, result, *, success=True):
        identifier = event.get("id")
        pending = self.tool_requests.pop(identifier, None)
        if pending != event or event.get("method") != "item/tool/call":
            raise WorkerRejected("tool_request_mismatch")
        await self._send({"id": identifier, "result": {"success": success,
            "contentItems": [{"type": "inputText", "text": json.dumps(result)}]}})

    async def question_result(self, event, answers):
        identifier = event.get("id")
        pending = self.tool_requests.pop(identifier, None)
        if pending != event or event.get("method") != "item/tool/requestUserInput":
            raise WorkerRejected("tool_request_mismatch")
        await self._send({"id": identifier, "result": {"answers": answers}})

    async def interrupt(self):
        if self.active:
            thread_id, turn_id = self.active
            await self._request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
            self.tool_requests.clear()
