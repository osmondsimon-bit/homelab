"""Relay one private Telegram conversation to normal Codex turns and approvals."""

import json
import os
import secrets
import shlex
import stat
from pathlib import Path
import sqlite3
import time

from .presentation import LOCAL_NOTICE, phone_text
from .normal_worker import WorkerRejected


class RelayRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Relay:
    def __init__(self, database: Path, user_id, chat_id, worker, *, home: Path, clock=time.time, offset=0):
        self.user_id, self.chat_id, self.worker, self.home, self.clock = user_id, chat_id, worker, home, clock
        parent = database.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise RelayRejected("private_state_permissions")
        descriptor = os.open(database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
                raise RelayRejected("private_state_permissions")
        finally:
            os.close(descriptor)
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        maximum = 64 * 1024 * 1024 // page_size
        if self.db.execute(f"PRAGMA max_page_count={maximum}").fetchone()[0] > maximum:
            raise RelayRejected("state_capacity")
        self.db.execute("PRAGMA wal_autocheckpoint=128")
        self.db.executescript("CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT);"
                              "CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,body TEXT);")
        if self._get("offset") is None:
            with self.db:
                self._set("offset", offset)
        if self._get("activity", "idle") != "idle":
            with self.db:
                self._set("paused", True)
                self._set("activity", "idle")
                self._set("pending", None)
                self._set("turn", None)
                self._reply("The previous task was interrupted. Relay paused; inspect its outcome before /resume. Nothing was replayed.")
        if self._get("paused", False):
            with self.db:
                self._set("resume_after", int(self.clock()))

    def close(self):
        self.db.close()

    def _get(self, key, default=None):
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (key, json.dumps(value)))

    def _reply(self, text, *, exact=False, **extra):
        if self._full():
            return
        body = {"chat_id": self.chat_id, "text": text if exact else phone_text(text, home=self.home), **extra}
        self.db.execute("INSERT INTO outbox(body) VALUES(?)", (json.dumps(body),))

    def _full(self):
        return self.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] >= 128

    def outbox(self):
        return [(identifier, json.loads(body)) for identifier, body in self.db.execute("SELECT id,body FROM outbox ORDER BY id LIMIT 128")]

    def sent(self, identifier):
        with self.db:
            self.db.execute("DELETE FROM outbox WHERE id=?", (identifier,))

    def cursor(self):
        return self._get("offset", 0)

    async def _dismiss(self):
        pending = self._get("pending")
        with self.db:
            self._set("pending", None)
            if pending:
                self._set("activity", "running")
        if pending:
            try:
                if pending["kind"] == "approval":
                    await self.worker.approve(pending["event"], False)
                else:
                    await self.worker.cancel_question(pending["event"])
            except WorkerRejected as error:
                if error.code not in {"approval_mismatch", "question_mismatch"}:
                    raise

    async def tick(self):
        pending = self._get("pending")
        if pending and self.clock() >= pending["expires"]:
            await self._dismiss()
            with self.db:
                self._reply("The approval or question expired and was declined.")

    async def _control(self, text, stamp):
        if text not in {"/status", "/pause", "/resume", "/stop", "/new", "/start", "/help"}:
            return False
        if text in {"/start", "/help"}:
            with self.db:
                self._reply("Send a task in plain language. /status shows activity; /pause blocks new tasks; /resume allows fresh tasks; /stop interrupts and pauses; /new starts a new conversation when idle.")
        elif text == "/status":
            with self.db:
                self._reply(("Paused. " if self._get("paused", False) else "Ready. ") + self._get("activity", "idle") + ".")
        elif text in {"/pause", "/stop"}:
            with self.db:
                self._set("paused", True)
                self._set("resume_after", int(self.clock()))
            await self._dismiss()
            if text == "/stop" and self._get("turn"):
                try:
                    await self.worker.interrupt()
                except WorkerRejected as error:
                    if error.code != "turn_not_active":
                        raise
            with self.db:
                self._reply("Paused. " + ("Interrupt requested; already completed effects remain. Inspect actual state before retrying." if text == "/stop" else "An active task can finish. Use /stop to request interruption."))
        elif text == "/resume":
            with self.db:
                if stamp <= self._get("resume_after", -1):
                    self._reply("That resume predates the pause or recovery. Review current state, then send a fresh /resume.")
                else:
                    self._set("paused", False)
                    self._reply("Resumed. Send a fresh request; previous work is not replayed.")
        elif text == "/new":
            with self.db:
                if self._get("activity", "idle") != "idle":
                    self._reply("Wait for the active task or use /stop first.")
                else:
                    self._set("thread", None)
                    self._reply("The next request will start a new Codex conversation.")
        return True

    def _owner(self, sender, chat):
        return (isinstance(sender, dict) and isinstance(chat, dict) and type(sender.get("id")) is int
                and type(chat.get("id")) is int and sender["id"] == self.user_id
                and chat["id"] == self.chat_id and chat.get("type") == "private")

    def _approval_text(self, event):
        params, method = event["params"], event["method"]
        item = self._get("items", {}).get(params.get("itemId"), {})
        parts = ["Codex requests approval."]
        if method == "item/commandExecution/requestApproval":
            command = params.get("command") or item.get("command")
            if isinstance(command, list) and all(isinstance(word, str) for word in command):
                command = shlex.join(command)
            if not isinstance(command, str) or not command:
                return LOCAL_NOTICE
            cwd = params.get("cwd") or item.get("cwd")
            if not isinstance(cwd, str) or not Path(cwd).is_absolute():
                return LOCAL_NOTICE
            parts.append("Command: " + command)
            parts.append("Directory: " + cwd)
        elif method == "item/fileChange/requestApproval":
            changes = item.get("changes", [])
            if not item.get("diffAvailable") or not changes:
                return LOCAL_NOTICE
            for change in changes:
                if not isinstance(change.get("path"), str) or not isinstance(change.get("diff"), str):
                    return LOCAL_NOTICE
                parts.append("File: " + change["path"])
                parts.append("Change: " + json.dumps(change.get("kind"), sort_keys=True))
                parts.append(change["diff"])
            if params.get("grantRoot"):
                parts.append("Write location: " + str(params["grantRoot"]))
        elif method == "item/permissions/requestApproval":
            parts.append("Permissions for this turn: " + json.dumps(params.get("permissions", {}), sort_keys=True))
        else:
            return LOCAL_NOTICE
        if isinstance(params.get("reason"), str):
            parts.append("Reason: " + params["reason"])
        if params.get("additionalPermissions"):
            parts.append("Additional permissions: " + json.dumps(params["additionalPermissions"], sort_keys=True))
        if params.get("networkApprovalContext"):
            parts.append("Network scope: " + json.dumps(params["networkApprovalContext"], sort_keys=True))
        parts.append("Expires in ten minutes.")
        original = "\n".join(parts)
        rendered = phone_text(original, truncate=False)
        return rendered if original == rendered else LOCAL_NOTICE

    async def _callback(self, query):
        if not self._owner(query.get("from"), query.get("message", {}).get("chat")):
            return
        pending, data = self._get("pending"), query.get("data")
        if (not pending or pending.get("kind") != "approval" or not isinstance(data, str)
                or data not in {"a:" + pending["nonce"], "d:" + pending["nonce"]}
                or self.clock() >= pending["expires"] or self._get("paused", False)):
            with self.db:
                self._reply("That approval is expired or no longer available.")
            return
        with self.db:
            self._set("pending", None)
            self._set("activity", "running")
        try:
            await self.worker.approve(pending["event"], data.startswith("a:"))
        except WorkerRejected as error:
            if error.code != "approval_mismatch":
                raise
            with self.db:
                self._reply("That native approval is no longer available.")

    def _question_text(self, pending):
        questions = pending["event"]["params"]["questions"]
        question = questions[pending["index"]]
        options = question.get("options") or []
        if (question.get("isSecret") is True or not isinstance(question.get("question"), str)
                or not isinstance(options, list) or len(options) > 20):
            return LOCAL_NOTICE
        parts = [f"Codex asks ({pending['index'] + 1}/{len(questions)}): " + question["question"]]
        for number, option in enumerate(options, 1):
            if not isinstance(option, dict) or not isinstance(option.get("label"), str):
                return LOCAL_NOTICE
            parts.append(f"{number}. " + option["label"] + (": " + option["description"] if isinstance(option.get("description"), str) else ""))
        parts.append("Reply with an option number or your answer. Expires in ten minutes. /stop interrupts.")
        return phone_text("\n".join(parts), home=self.home, truncate=False)

    async def _answer(self, text):
        pending = self._get("pending")
        if not pending or pending.get("kind") != "question":
            return False
        if self.clock() >= pending["expires"]:
            await self.tick()
            return True
        question = pending["event"]["params"]["questions"][pending["index"]]
        options = question.get("options") or []
        if text.isdecimal() and 1 <= int(text) <= len(options):
            text = options[int(text) - 1]["label"]
        pending["answers"][question["id"]] = {"answers": [text]}
        pending["index"] += 1
        if pending["index"] == len(pending["event"]["params"]["questions"]):
            with self.db:
                self._set("pending", None)
                self._set("activity", "running")
            await self.worker.answer_question(pending["event"], pending["answers"])
        else:
            text = self._question_text(pending)
            if text == LOCAL_NOTICE:
                await self._dismiss()
                with self.db:
                    self._reply("This question needs local review. It was dismissed here.")
            else:
                with self.db:
                    self._set("pending", pending)
                    self._reply(text)
        return True

    async def event(self, event):
        params, method = event.get("params", {}), event.get("method")
        turn = params.get("turn", {}).get("id") if method == "turn/completed" else params.get("turnId")
        if not turn or (params.get("threadId"), turn) != (self._get("thread"), self._get("turn")):
            return
        if "id" in event:
            if self._get("paused", False) or self._get("pending") or self._full():
                if method == "item/tool/requestUserInput":
                    await self.worker.cancel_question(event)
                else:
                    await self.worker.approve(event, False)
                return
            if method != "item/tool/requestUserInput":
                text = self._approval_text(event)
                if text == LOCAL_NOTICE:
                    await self.worker.approve(event, False)
                    with self.db:
                        self._reply("This approval needs local review. It was declined here.")
                    return
                nonce = secrets.token_urlsafe(18)
                with self.db:
                    self._set("pending", {"kind": "approval", "nonce": nonce, "event": event, "expires": self.clock() + 600})
                    self._set("activity", "awaiting_approval")
                    self._reply(text, exact=True, reply_markup={"inline_keyboard": [[
                        {"text": "Approve", "callback_data": "a:" + nonce}, {"text": "Decline", "callback_data": "d:" + nonce}]]})
            else:
                questions = params.get("questions")
                if (not isinstance(questions, list) or not 1 <= len(questions) <= 8
                        or any(not isinstance(q, dict) or not isinstance(q.get("id"), str) for q in questions)
                        or len({q["id"] for q in questions}) != len(questions)):
                    await self.worker.cancel_question(event)
                    return
                pending = {"kind": "question", "event": event, "index": 0, "answers": {}, "expires": self.clock() + 600}
                text = self._question_text(pending)
                if text == LOCAL_NOTICE:
                    await self.worker.cancel_question(event)
                    with self.db:
                        self._reply("This question needs local review. It was dismissed here.")
                    return
                with self.db:
                    self._set("pending", pending)
                    self._set("activity", "awaiting_answer")
                    self._reply(text)
            return
        item = params.get("item", {})
        if method in {"item/started", "item/completed"} and isinstance(item, dict):
            if method == "item/completed" and item.get("type") == "agentMessage":
                with self.db:
                    self._set("summary", phone_text(item.get("text"), home=self.home))
            elif item.get("type") in {"commandExecution", "fileChange"}:
                items = self._get("items", {})
                items[item.get("id")] = {"command": item.get("command"), "cwd": item.get("cwd"),
                    "changes": item.get("changes", []), "diffAvailable": item.get("diffAvailable", False)}
                with self.db:
                    self._set("items", dict(list(items.items())[-64:]))
        elif method == "turn/completed":
            with self.db:
                self._set("activity", "idle")
                self._set("pending", None)
                self._set("turn", None)
                if params.get("turn", {}).get("status") == "completed":
                    self._reply(self._get("summary") or "Codex finished. No summary was supplied.")
                else:
                    self._reply("Codex stopped or failed. Check the actual state before retrying a change.")

    async def handle(self, update):
        identifier = update.get("update_id")
        if type(identifier) is not int or identifier < self.cursor() or not 0 <= identifier < 2**63 - 1:
            return
        with self.db:
            self._set("offset", identifier + 1)
        if isinstance(update.get("callback_query"), dict):
            await self._callback(update["callback_query"])
            return
        message = update.get("message", {})
        if not isinstance(message, dict) or not self._owner(message.get("from"), message.get("chat")):
            return
        text, stamp = message.get("text"), message.get("date")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            return
        if type(stamp) is not int or not -60 <= self.clock() - stamp <= 600:
            with self.db:
                self._reply("That message is stale. Send a fresh request.")
            return
        if await self._control(text.strip(), stamp):
            return
        if self._full():
            return
        if self._get("paused", False):
            with self.db:
                self._reply("Relay paused. Inspect previous work if needed, then /resume and send a fresh request.")
            return
        if await self._answer(text):
            return
        if self._get("activity", "idle") != "idle":
            with self.db:
                self._reply("A task is active. Wait for the result or use /stop.")
            return
        with self.db:
            self._set("activity", "starting")
            self._set("summary", None)
            self._set("items", {})
        try:
            thread, turn = await self.worker.begin(text, self._get("thread"))
        except Exception:
            with self.db:
                self._set("activity", "idle")
                self._set("paused", True)
                self._set("turn", None)
                self._reply("Codex could not confirm starting this task. Relay paused. Check locally before retrying; no automatic replay.")
            raise RelayRejected("turn_start_uncertain") from None
        with self.db:
            self._set("thread", thread)
            self._set("turn", turn)
            self._set("activity", "running")
            self._reply("Working on it.")
