"""Bridge a normal user-owned Codex stdio session to a subscription-only relay."""

import asyncio
import contextlib
import json
import os
from pathlib import Path

from .authentication import AuthenticationRejected, require_subscription


class WorkerRejected(Exception):
    """Expose a safe category without server errors, stderr or native tool output."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class NormalWorker:
    """Retain normal tools/settings; keep account checks outside model control."""

    APPROVALS = frozenset({"item/commandExecution/requestApproval", "item/fileChange/requestApproval",
                          "item/permissions/requestApproval"})
    QUESTION = "item/tool/requestUserInput"
    PHONE_GUIDANCE = (
        "Follow repository AGENTS.md, accepted architecture decisions and relevant runbooks. "
        "Retain normal Codex tools and usual approvals. This conversation is relayed to a phone: "
        "give concise final summaries using service and host aliases; do not include raw IP addresses, "
        "logs or secrets. Never read or edit the Telegram relay state or token files. "
        "Do not replay actions with uncertain outcomes: inspect the affected system's state and "
        "report uncertainty before deciding what to do next."
    )

    def __init__(self, launcher, context: Path, workspace: Path, *, inherited=None):
        self.launcher = tuple(launcher)
        self.context, self.workspace = Path(context), Path(workspace)
        source = os.environ if inherited is None else inherited
        routing = {"OPENAI_API_BASE", "CHATGPT_BASE_URL", "CODEX_API_KEY", "CODEX_MODEL_PROVIDER",
                   "CODEX_PROVIDER", "CODEX_BASE_URL", "CODEX_AUTH_JSON", "CODEX_CHATGPT_BASE_URL",
                   "CODEX_OPENAI_BASE_URL"}
        self.environment = {key: value for key, value in source.items()
            if not key.upper().startswith("OPENAI_") and key.upper() not in routing}
        code_home = source.get("CODEX_HOME") or str(self.context / ".codex")
        if not isinstance(code_home, str) or not Path(code_home).is_absolute():
            raise WorkerRejected("worker_context_invalid")
        self.environment.update(HOME=str(self.context), CODEX_HOME=code_home)
        self.process = self.reader = None
        self.pending = {}
        self.events = asyncio.Queue(maxsize=256)
        self.sequence = 0
        self.active = None
        self.failed = False
        self.server_requests = {}
        self.seen_requests = set()
        self.starting = False
        self.interrupting = False
        self.ready = asyncio.Event()
        self.ready.set()

    async def __aenter__(self):
        arguments = list(self.launcher)
        for override in ('forced_login_method="chatgpt"', 'model_provider="openai"',
                         'chatgpt_base_url="https://chatgpt.com/backend-api"',
                         'openai_base_url="https://api.openai.com/v1"'):
            arguments.extend(["-c", override])
        arguments.extend(["app-server", "--listen", "stdio://"])
        try:
            self.process = await asyncio.create_subprocess_exec(*arguments, cwd=self.workspace,
                env=self.environment, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=1_000_000)
        except OSError:
            raise WorkerRejected("worker_unavailable") from None
        self.reader = asyncio.create_task(self._read())
        try:
            await self._request("initialize", {"clientInfo": {"name": "homelab-telegram", "version": "1"},
                "capabilities": {"experimentalApi": True, "requiredHumanApproval": True}})
            await self._send({"method": "initialized"})
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *_arguments):
        if self.process and self.process.stdin:
            self.process.stdin.close()
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), 2)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        self.process.kill()
                    await self.process.wait()
        if self.reader:
            self.reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.reader

    async def _send(self, message):
        if not self.process or self.process.returncode is not None:
            raise WorkerRejected("worker_unavailable")
        try:
            self.process.stdin.write(json.dumps(message).encode() + b"\n")
            await self.process.stdin.drain()
        except (OSError, ConnectionError):
            raise WorkerRejected("worker_unavailable") from None

    async def _request(self, method, params):
        self.sequence += 1
        identifier = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            await self._send({"id": identifier, "method": method, "params": params})
            return await asyncio.wait_for(future, 30)
        except TimeoutError:
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
                            result = message.get("result")
                            if not isinstance(result, dict):
                                future.set_exception(WorkerRejected("worker_protocol"))
                            else:
                                future.set_result(result)
                elif isinstance(message.get("method"), str):
                    visible = message if "id" in message else self._visible_notification(message)
                    if visible is not None:
                        self.events.put_nowait(visible)
        except (ValueError, OSError, asyncio.QueueFull):
            pass
        finally:
            self.failed = True
            with contextlib.suppress(asyncio.QueueFull):
                self.events.put_nowait({"method": "worker/failed"})
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(WorkerRejected("worker_unavailable"))

    @staticmethod
    def _visible_notification(message):
        """Discard streaming tool output before it consumes relay queue capacity."""
        method, params = message.get("method"), message.get("params")
        if not isinstance(params, dict):
            return None
        if method == "turn/completed" and isinstance(params.get("turn"), dict):
            turn = params["turn"]
            safe_turn = {key: turn[key] for key in ("id", "status") if key in turn}
            if turn.get("error"):
                safe_turn["error"] = {"message": "worker_turn_failed"}
            return {"method": method, "params": {"threadId": params.get("threadId"), "turn": safe_turn}}
        if method not in {"item/started", "item/completed"}:
            return None
        item = params.get("item")
        if not isinstance(item, dict) or item.get("type") not in {"agentMessage", "commandExecution", "fileChange"}:
            return None
        fields = {"id", "type", "command", "cwd"}
        if item["type"] == "agentMessage":
            fields.add("text")
        safe_item = {key: value for key, value in item.items() if key in fields}
        if item["type"] == "fileChange":
            proposed = item.get("changes")
            available = (isinstance(proposed, list) and bool(proposed)
                         and all(isinstance(change, dict) and isinstance(change.get("diff"), str)
                                 for change in proposed)
                         and sum(len(change["diff"]) for change in proposed) <= 6000)
            safe_item["diffAvailable"] = available
            changes = []
            for change in proposed if isinstance(proposed, list) else []:
                if not isinstance(change, dict):
                    continue
                safe_change = {"path": change["path"]} if isinstance(change.get("path"), str) else {}
                kind = change.get("kind")
                if isinstance(kind, dict):
                    safe_change["kind"] = {key: value for key, value in kind.items() if key in {"type", "movePath"}}
                if available:
                    safe_change["diff"] = change["diff"]
                changes.append(safe_change)
            safe_item["changes"] = changes
        return {"method": method, "params": {"threadId": params.get("threadId"),
            "turnId": params.get("turnId"), "item": safe_item}}

    async def begin(self, text, thread_id=None):
        if self.active or self.starting:
            raise WorkerRejected("turn_already_active")
        if not isinstance(text, str) or not text.strip() or (thread_id is not None
                and (not isinstance(thread_id, str) or not thread_id)):
            raise WorkerRejected("turn_input_invalid")
        self.starting = True
        self.ready.clear()
        try:
            return await self._begin(text, thread_id)
        finally:
            self.starting = False
            self.ready.set()

    async def _begin(self, text, thread_id):
        account = await self._request("account/read", {"refreshToken": False})
        identity = account.get("account")
        if (account.get("requiresOpenaiAuth") is not True or not isinstance(identity, dict)
                or identity.get("type") != "chatgpt"):
            raise AuthenticationRejected("subscription_required")
        limits = await self._request("account/rateLimits/read", {})
        require_subscription(account, limits)
        params = {"cwd": str(self.workspace), "modelProvider": "openai",
                  "developerInstructions": self.PHONE_GUIDANCE}
        if thread_id is None:
            params["allowProviderModelFallback"] = False
            thread = await self._request("thread/start", params)
        else:
            params["threadId"] = thread_id
            thread = await self._request("thread/resume", params)
        identifier = thread.get("thread", {}).get("id") if isinstance(thread.get("thread"), dict) else None
        if not isinstance(identifier, str) or not identifier or thread.get("modelProvider") != "openai":
            raise WorkerRejected("worker_protocol")
        result = await self._request("turn/start", {"threadId": identifier,
            "input": [{"type": "text", "text": text}]})
        turn_id = result.get("turn", {}).get("id") if isinstance(result.get("turn"), dict) else None
        if not isinstance(turn_id, str) or not turn_id:
            raise WorkerRejected("worker_protocol")
        self.active = (identifier, turn_id)
        self.interrupting = False
        self.seen_requests.clear()
        return self.active

    async def next_event(self):
        while True:
            await self.ready.wait()
            if self.failed:
                raise WorkerRejected("worker_unavailable")
            event = await self.events.get()
            await self.ready.wait()
            if event.get("method") == "worker/failed":
                raise WorkerRejected("worker_unavailable")
            params = event.get("params", {})
            if not isinstance(params, dict):
                raise WorkerRejected("worker_protocol")
            if "id" in event:
                identifier = event["id"]
                if type(identifier) not in {str, int}:
                    raise WorkerRejected("worker_protocol")
                if (identifier in self.seen_requests or len(self.seen_requests) >= 256
                        or event.get("method") not in self.APPROVALS | {self.QUESTION}
                        or not self.active or self.interrupting or not isinstance(params.get("itemId"), str)
                        or (params.get("threadId"), params.get("turnId")) != self.active):
                    await self._send({"id": identifier, "error": {"code": -32601, "message": "request not supported"}})
                    raise WorkerRejected("worker_request_not_allowed")
                self.server_requests[identifier] = json.loads(json.dumps(event))
                self.seen_requests.add(identifier)
                return event
            if event.get("method") == "turn/completed":
                turn = params.get("turn")
                if not isinstance(turn, dict) or not self.active or (
                        params.get("threadId"), turn.get("id")) != self.active:
                    continue
                self.active = None
                self.server_requests.clear()
                return event
            if not self.active or (params.get("threadId"), params.get("turnId")) != self.active:
                continue
            if event.get("method") in {"item/started", "item/completed"}:
                return event

    async def interrupt(self):
        """Ask Codex to interrupt; native processes may already have produced effects."""
        if not self.active:
            raise WorkerRejected("turn_not_active")
        thread_id, turn_id = self.active
        self.interrupting = True
        self.server_requests.clear()
        await self._request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})

    async def approve(self, event, accepted):
        if type(accepted) is not bool or not isinstance(event, dict):
            raise WorkerRejected("approval_invalid")
        original = self.server_requests.get(event.get("id")) if type(event.get("id")) in {str, int} else None
        if original != event or original is None or (
                event["params"].get("threadId"), event["params"].get("turnId")) != self.active or event.get("method") not in self.APPROVALS:
            raise WorkerRejected("approval_mismatch")
        if event["method"] == "item/permissions/requestApproval":
            requested = event["params"].get("permissions")
            if not isinstance(requested, dict) or set(requested) - {"network", "fileSystem"}:
                raise WorkerRejected("approval_invalid")
            result = {"permissions": requested if accepted else {}, "scope": "turn"}
        else:
            decision = "accept" if accepted else "decline"
            available = event["params"].get("availableDecisions")
            if available is not None and (not isinstance(available, list) or decision not in available):
                raise WorkerRejected("approval_decision_unavailable")
            result = {"decision": decision}
        del self.server_requests[event["id"]]
        await self._send({"id": event["id"], "result": result})

    def _question(self, event):
        if not isinstance(event, dict) or event.get("method") != self.QUESTION:
            raise WorkerRejected("question_mismatch")
        original = self.server_requests.get(event.get("id")) if type(event.get("id")) in {str, int} else None
        if original is None or original != event or (
                event["params"].get("threadId"), event["params"].get("turnId")) != self.active:
            raise WorkerRejected("question_mismatch")

    async def cancel_question(self, event):
        """Dismiss a pending native question using its valid empty answer map."""
        self._question(event)
        del self.server_requests[event["id"]]
        await self._send({"id": event["id"], "result": {"answers": {}}})

    async def answer_question(self, event, answers):
        self._question(event)
        questions = event["params"].get("questions")
        if (not isinstance(questions, list) or not questions or not isinstance(answers, dict)
                or any(not isinstance(question, dict) or not isinstance(question.get("id"), str)
                       for question in questions)
                or set(answers) != {question.get("id") for question in questions}
                or any(not isinstance(value, dict) or set(value) != {"answers"}
                    or not isinstance(value["answers"], list) or not 1 <= len(value["answers"]) <= 32
                    or any(not isinstance(answer, str) or len(answer) > 8000 for answer in value["answers"])
                    for value in answers.values())
                or len(json.dumps(answers)) > 65536):
            raise WorkerRejected("question_answers_invalid")
        del self.server_requests[event["id"]]
        await self._send({"id": event["id"], "result": {"answers": answers}})
