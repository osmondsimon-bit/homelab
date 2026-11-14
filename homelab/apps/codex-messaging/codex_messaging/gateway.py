"""Authorise private-chat input and journal work before contacting the worker."""

import json
import contextlib
import os
import sqlite3
import time
from pathlib import Path

from .authentication import AuthenticationRejected
from .operations import PolicyError
from .presentation import LOCAL_NOTICE, safe_text
from .rpc import WorkerRejected

class Coordinator:
    """Own the durable chat boundary, separately from model and operation authority."""

    def __init__(self, database: Path, user_id: int, chat_id: int, worker, broker, *, clock=time.time, mode="keyless"):
        self.user_id, self.chat_id = user_id, chat_id
        self.worker, self.broker, self.clock = worker, broker, clock
        if mode not in {"keyless", "operational"}:
            raise ValueError("gateway_mode")
        self.mode = mode
        self.database = sqlite3.connect(database)
        os.chmod(database, 0o600)
        self.database.execute("PRAGMA journal_mode=WAL")
        self.database.execute("PRAGMA synchronous=FULL")
        self.database.executescript("""
            CREATE TABLE IF NOT EXISTS inbox (id INTEGER PRIMARY KEY, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if self._get("activity") in {"starting", "running", "awaiting_approval", "awaiting_question", "awaiting_diagnostic", "dispatching"}:
            with self.database:
                self._set("activity", "review_required")
                self._set("paused", True)
                self._set("pending", None)

    def close(self):
        self.database.close()

    def outbox(self):
        return [(identifier, json.loads(body)) for identifier, body in self.database.execute("SELECT id,body FROM outbox ORDER BY id")]

    def sent(self, identifier):
        with self.database:
            self.database.execute("DELETE FROM outbox WHERE id=?", (identifier,))

    def cursor(self):
        return self.database.execute("SELECT COALESCE(MAX(id)+1,0) FROM inbox").fetchone()[0]

    def _get(self, key, default=None):
        row = self.database.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _set(self, key, value):
        self.database.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, json.dumps(value)))

    def _reply(self, text, **extra):
        body = {"chat_id": self.chat_id, "text": safe_text(text), **extra}
        self.database.execute("INSERT INTO outbox(body) VALUES(?)", (json.dumps(body),))

    async def _command(self, command):
        if command == "/pause":
            await self.broker.pause()
            with self.database:
                self._set("paused", True)
                self._reply("Changes paused. Read-only investigation remains available.")
        elif command == "/resume":
            if self.mode == "keyless":
                with self.database:
                    self._reply("Keyless test mode has no operational authority. Changes remain disabled.")
                return
            await self.broker.resume()
            with self.database:
                self._set("paused", False)
                self._reply("Changes enabled. Stopped or uncertain tasks are not replayed.")
        elif command == "/status":
            with self.database:
                self._reply("Task: " + self._get("activity", "idle") + ". Changes: "
                            + ("paused." if self._get("paused", True) else "enabled."))
        elif command == "/stop":
            await self.broker.stop()
            await self.worker.interrupt()
            with self.database:
                self._set("paused", True)
                self._set("activity", "stopped")
                self._set("turn_id", None)
                self._set("pending", None)
                self._reply("Stop requested; no further steps will start. A package step already running may finish safely.")
        elif command == "/new" and self._get("activity") in {None, "idle", "stopped", "failed"} and not self._get("pending"):
            with self.database:
                self._set("thread_id", None)
                self._set("turn_id", None)
                self._set("activity", "idle")
                self._reply("New conversation selected. Send a task using logical target names.")
        else:
            with self.database:
                self._reply("Use /new, /status, /pause, /resume or /stop. Stop an active task before starting a new conversation.")

    async def startup(self):
        await self.broker.pause()
        with self.database:
            self._set("paused", True)
        jobs = await self.broker.recoverable_jobs()
        if jobs:
            with self.database:
                self._set("activity", "review_required")
                self._reply("Earlier jobs need review. Changes remain paused; no operation will be replayed.")

    async def maintain(self):
        """Run bounded retention while serial chat handling cannot start another turn."""
        if (self._get("activity", "idle") not in {"idle", "stopped", "failed"}
                or self._get("pending") or self.clock() - self._get("last_retention", 0) < 86400
                and self._get("last_retention") is not None):
            return
        if await self.broker.recoverable_jobs():
            return
        before = self.clock() - 30 * 86400
        await self.worker.prune_inactive(before)
        with self.database:
            if self._get("thread_touched", 0) < before:
                self._set("thread_id", None)
                self._set("turn_id", None)
            self.database.execute("DELETE FROM inbox WHERE created < ? AND id < (SELECT MAX(id) FROM inbox)",
                                  (self.clock() - 90 * 86400,))
            self._set("last_retention", self.clock())

    async def tick(self):
        pending = self._get("pending")
        if pending and pending.get("kind") == "diagnostic":
            result = await self.broker.reconcile(pending["job_id"])
            if result["state"] not in {"running", "dispatching"} or self.clock() >= pending["expires_at"]:
                success = result["state"] == "completed"
                if not success:
                    result = {"state": "review_required", "job_id": pending["job_id"]}
                with self.database:
                    self._set("pending", None)
                    self._set("activity", "running")
                await self.worker.tool_result(pending["event"], result, success=success)
        if pending and pending.get("kind") == "approval" and pending.get("state") == "pending" and self.clock() >= pending["expires_at"]:
            with self.database:
                self._set("pending", None)
                self._set("activity", "running")
                self._reply("Approval expired. No operation was started from that approval.")
            await self.worker.tool_result(pending["event"], {"state": "expired"}, success=False)
        if self.mode == "keyless":
            return
        jobs = await self.broker.recoverable_jobs()
        known = self._get("known_jobs", {})
        for job in jobs:
            if job["state"] in {"running", "dispatching"}:
                job = await self.broker.reconcile(job["job_id"])
            if known.get(job["job_id"]) != job["state"]:
                with self.database:
                    self._reply("Operation on " + job["target_id"] + ": " + job["state"].replace("_", " ") + ".")
                    known[job["job_id"]] = job["state"]
                    self._set("known_jobs", known)
                    if job["job_id"] == self._get("job_id"):
                        self._set("job_state", job["state"])

    async def _callback(self, callback):
        if (callback.get("from", {}).get("id") != self.user_id
                or callback.get("message", {}).get("chat", {}).get("id") != self.chat_id
                or callback.get("message", {}).get("chat", {}).get("type") != "private"):
            return
        pending = self._get("pending")
        if (not pending or pending.get("kind") != "approval" or pending.get("state") != "pending"
                or callback.get("data") != "approve:" + pending["approval_id"]
                or self.clock() >= pending["expires_at"] or self._get("paused", True)):
            with self.database:
                self._reply("Approval is unavailable, expired or paused. Request a fresh plan.")
            return
        pending["state"] = "approving"
        with self.database:
            self._set("pending", pending)
            self._set("activity", "dispatching")
        try:
            job = await self.broker.approve(self.user_id, self.chat_id, pending["approval_id"], pending["plan_digest"])
        except PolicyError as error:
            with self.database:
                self._set("pending", None)
                self._set("activity", "running")
                self._reply("Operation was not started. A fresh plan or local review is required.")
            await self.worker.tool_result(pending["event"], {"state": "rejected", "code": error.code}, success=False)
            return
        except (ConnectionError, OSError, TimeoutError):
            with contextlib.suppress(ConnectionError, OSError, TimeoutError, PolicyError):
                await self.broker.pause()
            with self.database:
                self._set("paused", True)
                self._set("activity", "review_required")
                self._reply("Dispatch outcome is uncertain. Changes are paused; review the original job before continuing.")
            await self.worker.tool_result(pending["event"], {"state": "uncertain"}, success=False)
            return
        with self.database:
            self._set("job_id", job["job_id"])
            self._set("job_state", job["state"])
            self._set("pending", None)
            self._set("activity", "running")
            self._reply("Operation accepted. Verification is still pending.")
        await self.worker.tool_result(pending["event"], job)

    async def worker_event(self, event):
        method, parameters = event.get("method"), event.get("params", {})
        if method in {"item/completed", "turn/completed"}:
            turn = parameters.get("turn", {}).get("id") if method == "turn/completed" else parameters.get("turnId")
            if (parameters.get("threadId"), turn) != (self._get("thread_id"), self._get("turn_id")) or not turn:
                return
        if "id" in event and (parameters.get("threadId"), parameters.get("turnId")) != (self._get("thread_id"), self._get("turn_id")):
            raise WorkerRejected("tool_request_mismatch")
        if method == "item/tool/call":
            arguments = parameters.get("arguments")
            tool = parameters.get("tool")
            if (not isinstance(arguments, dict) or parameters.get("namespace") not in {None, ""}
                    or tool not in {"diagnose", "propose_operation"}
                    or not set(arguments) <= ({"target", "probe", "unit"} if tool == "diagnose" else {"target", "operation", "unit"})
                    or not isinstance(arguments.get("target"), str)
                    or any(not isinstance(value, str) for value in arguments.values())):
                await self.worker.tool_result(event, {"state": "rejected", "code": "tool_not_allowed"}, success=False)
                return
            options = {key: value for key, value in arguments.items() if key not in {"target", "operation"}}
            try:
                if tool == "diagnose":
                    job = await self.broker.diagnose(self.user_id, self.chat_id, arguments["target"], options)
                    if job["state"] in {"running", "dispatching"}:
                        with self.database:
                            self._set("pending", {"kind": "diagnostic", "event": event, "job_id": job["job_id"],
                                                  "expires_at": self.clock() + 600})
                            self._set("activity", "awaiting_diagnostic")
                    else:
                        await self.worker.tool_result(event, job, success=job["state"] == "completed")
                    return
                if self._get("paused", True) or self._get("pending"):
                    raise PolicyError("changes_paused")
                prepared = await self.broker.prepare(self.user_id, self.chat_id, arguments["target"], arguments.get("operation"), options)
                plan = prepared["plan"]
                impact = "; ".join(plan["snapshot"]["impact"])
                verification = "; ".join(plan["snapshot"]["verification"])
                prompt = (f"Approve {plan['operation'].replace('_', ' ')} on {plan['target_id']}?\n"
                          f"Impact: {impact}\nVerify: {verification}\nExpires in ten minutes.")
                if safe_text(prompt) == LOCAL_NOTICE:
                    await self.broker.pause()
                    with self.database:
                        self._set("paused", True)
                    raise PolicyError("presentation_requires_local_review")
                pending = {"kind": "approval", "state": "pending", "event": event,
                           "approval_id": prepared["approval_id"], "plan_digest": prepared["plan_digest"],
                           "expires_at": prepared["expires_at"]}
                with self.database:
                    self._set("pending", pending)
                    self._set("activity", "awaiting_approval")
                    self._reply(prompt, reply_markup={"inline_keyboard": [[{"text": "Approve this plan", "callback_data": "approve:" + prepared["approval_id"]}]]})
            except PolicyError as error:
                await self.worker.tool_result(event, {"state": "rejected", "code": error.code}, success=False)
        elif method == "item/tool/requestUserInput":
            questions = parameters.get("questions", [])
            if (not isinstance(questions, list) or len(questions) != 1 or not isinstance(questions[0], dict)
                    or questions[0].get("isSecret") is True or not isinstance(questions[0].get("id"), str)
                    or not isinstance(questions[0].get("question"), str) or safe_text(questions[0]["question"]) == LOCAL_NOTICE):
                await self.worker.interrupt()
                with self.database:
                    self._set("activity", "review_required")
                    self._reply("This question needs local review. Task interrupted.")
                return
            with self.database:
                self._set("pending", {"kind": "question", "event": event, "question_id": questions[0]["id"]})
                self._set("activity", "awaiting_question")
                self._reply(questions[0]["question"])
        elif method == "item/completed" and parameters.get("item", {}).get("type") == "agentMessage":
            text = parameters["item"].get("text", "")
            try:
                summary = json.loads(text)["summary"]
            except (ValueError, KeyError, TypeError):
                summary = LOCAL_NOTICE
            with self.database:
                self._set("summary", safe_text(summary))
        elif method == "turn/completed":
            with self.database:
                self._set("activity", "idle")
                self._set("pending", None)
                if parameters.get("turn", {}).get("status") != "completed":
                    self._reply("Task interrupted or failed. Check status before requesting another change.")
                elif self._get("job_id"):
                    self._reply("Operation status: " + self._get("job_state", "review required").replace("_", " ") + ".")
                else:
                    self._reply("No operation was executed.\n" + self._get("summary", LOCAL_NOTICE))

    async def handle(self, update):
        identifier = update.get("update_id")
        if type(identifier) is not int or not 0 <= identifier < 2**63 - 1:
            return
        with self.database:
            if not self.database.execute("INSERT OR IGNORE INTO inbox(id,created) VALUES(?,?)", (identifier, self.clock())).rowcount:
                return
        if "callback_query" in update:
            await self._callback(update["callback_query"])
            return
        message = update.get("message", {})
        if (message.get("from", {}).get("id") != self.user_id
                or message.get("chat", {}).get("id") != self.chat_id
                or message.get("chat", {}).get("type") != "private"):
            return
        text = message.get("text")
        if (not isinstance(text, str) or not text.strip() or len(text) > 4000
                or any(name in message for name in ("document", "photo", "audio", "video", "voice", "location", "contact", "forward_origin"))):
            return
        timestamp = message.get("date")
        if type(timestamp) is not int or not -60 <= self.clock() - timestamp <= 600:
            with self.database:
                self._reply("This message is stale or has an invalid timestamp. Send a fresh request.")
            return
        if text.startswith("/"):
            await self._command(text.strip())
            return
        if safe_text(text) != text:
            with self.database:
                self._reply("Use logical target names and keep credentials, addresses and raw diagnostic dumps out of chat.")
            return
        pending = self._get("pending")
        if pending and pending.get("kind") == "question":
            await self.worker.question_result(pending["event"], {pending["question_id"]: {"answers": [text]}})
            with self.database:
                self._set("pending", None)
                self._set("activity", "running")
            return
        if self._get("activity") in {"starting", "running", "awaiting_approval", "awaiting_diagnostic", "dispatching"}:
            with self.database:
                self._reply("A task is active. Wait for its result or use /stop before starting another task.")
            return
        with self.database:
            self._set("activity", "starting")
            self._set("summary", None)
            self._set("job_id", None)
        try:
            thread_id, turn_id = await self.worker.begin(text, self._get("thread_id"))
        except (AuthenticationRejected, WorkerRejected):
            with self.database:
                self._set("activity", "failed")
                self._reply("Work stopped: subscription authentication, quota or worker availability needs local review.")
            return
        with self.database:
            self._set("thread_id", thread_id)
            self._set("thread_touched", self.clock())
            self._set("turn_id", turn_id)
            self._set("activity", "running")
            self._reply("Investigating. Changes will require a separate plan approval.")
