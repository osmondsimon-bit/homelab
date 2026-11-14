"""Test the private Telegram boundary around an ordinary Codex session."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.relay import Relay, RelayRejected


class Worker:
    def __init__(self):
        self.tasks, self.decisions, self.answers = [], [], []

    async def begin(self, text, thread_id=None):
        self.tasks.append((text, thread_id))
        return "thread", "turn"

    async def approve(self, event, accepted):
        self.decisions.append((event["id"], accepted))

    async def answer_question(self, event, answers):
        self.answers.append((event["id"], answers))

    async def interrupt(self):
        self.tasks.append(("interrupt", None))

    async def cancel_question(self, event):
        self.answers.append((event["id"], {}))


class RelayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "relay.sqlite"
        self.now, self.worker = 1000, Worker()
        self.relay = Relay(self.path, 101, 101, self.worker, home=Path("/home/operator"), clock=lambda: self.now)

    def tearDown(self):
        self.relay.close()
        self.temporary.cleanup()

    def message(self, identifier=1, text="Investigate the DNS server", user=101, chat=101, date=1000):
        return {"update_id": identifier, "message": {"from": {"id": user}, "chat": {"id": chat, "type": "private"}, "text": text, "date": date}}

    async def test_only_fresh_owner_messages_start_one_normal_codex_turn(self):
        await self.relay.handle(self.message(user=202))
        await self.relay.handle(self.message(2, chat=202))
        await self.relay.handle(self.message(3, date=0))
        await self.relay.handle(self.message(4))
        await self.relay.handle(self.message(4))
        await self.relay.handle(self.message(5, text="Start another task"))
        self.assertEqual(self.worker.tasks, [("Investigate the DNS server", None)])
        self.assertEqual(self.relay.cursor(), 6)

    async def test_native_command_approval_shows_command_and_directory_to_owner_once(self):
        await self.relay.handle(self.message())
        event = {"id": 900, "method": "item/commandExecution/requestApproval", "params": {
            "threadId": "thread", "turnId": "turn", "itemId": "command",
            "command": 'ssh media "systemctl restart jellyfin"', "cwd": "/home/operator"}}
        await self.relay.event(event)
        prompt = self.relay.outbox()[-1][1]
        self.assertIn("systemctl restart jellyfin", prompt["text"])
        self.assertIn("Directory: /home/operator", prompt["text"])
        data = prompt["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        def callback(identifier, user):
            return {"update_id": identifier, "callback_query": {"from": {"id": user},
                "message": {"chat": {"id": 101, "type": "private"}}, "data": data}}
        await self.relay.handle(callback(2, 202))
        self.assertEqual(self.worker.decisions, [])
        await self.relay.handle(callback(3, 101))
        await self.relay.handle(callback(4, 101))
        self.assertEqual(self.worker.decisions, [(900, True)])

    async def test_pause_stop_resume_and_restart_never_replay_an_uncertain_task(self):
        await self.relay.handle(self.message())
        await self.relay.handle(self.message(2, "/stop"))
        self.assertEqual(self.worker.tasks[-1], ("interrupt", None))
        self.relay.close()
        self.relay = Relay(self.path, 101, 101, self.worker, home=Path("/home/operator"), clock=lambda: self.now)
        await self.relay.handle(self.message(3, "reboot dns"))
        self.assertEqual(len(self.worker.tasks), 2)
        await self.relay.handle(self.message(4, "/status"))
        self.assertIn("paused", self.relay.outbox()[-1][1]["text"].lower())
        self.now = 1001
        await self.relay.handle(self.message(5, "/resume", date=1001))
        await self.relay.handle(self.message(6, "Inspect the current DNS state", date=1001))
        self.assertEqual(self.worker.tasks[-1], ("Inspect the current DNS state", "thread"))

    async def test_native_questions_collect_owner_answers_then_expire_without_hanging(self):
        await self.relay.handle(self.message())
        event = {"id": 901, "method": "item/tool/requestUserInput", "params": {
            "threadId": "thread", "turnId": "turn", "itemId": "question", "questions": [
                {"id": "scope", "question": "Which service?", "options": [{"label": "DNS"}, {"label": "Media"}]},
                {"id": "timing", "question": "When should maintenance run?", "options": []}]}}
        await self.relay.event(event)
        self.assertIn("Which service?", self.relay.outbox()[-1][1]["text"])
        await self.relay.handle(self.message(2, "2", user=202))
        await self.relay.handle(self.message(3, "1"))
        self.assertEqual(self.worker.answers, [])
        await self.relay.handle(self.message(4, "After midnight"))
        self.assertEqual(self.worker.answers, [(901, {"scope": {"answers": ["DNS"]}, "timing": {"answers": ["After midnight"]}})])
        event["id"] = 902
        await self.relay.event(event)
        self.now = 1601
        await self.relay.tick()
        self.assertEqual(self.worker.answers[-1], (902, {}))

    async def test_approval_with_hidden_target_is_declined_instead_of_approving_redacted_scope(self):
        await self.relay.handle(self.message())
        await self.relay.event({"id": 903, "method": "item/commandExecution/requestApproval", "params": {
            "threadId": "thread", "turnId": "turn", "itemId": "command",
            "command": 'ssh root@192.0.2.23 "systemctl restart jellyfin"', "cwd": "/home/operator"}})
        self.assertEqual(self.worker.decisions, [(903, False)])
        self.assertNotIn("192.0.2.23", str(self.relay.outbox()))
        self.assertNotIn("reply_markup", self.relay.outbox()[-1][1])

    async def test_file_approval_shows_the_entire_proposed_patch(self):
        await self.relay.handle(self.message())
        await self.relay.event({"method": "item/started", "params": {"threadId": "thread", "turnId": "turn", "item": {
            "id": "edit", "type": "fileChange", "diffAvailable": True, "changes": [{"path": "/fixture/config",
                "kind": {"type": "update", "movePath": None}, "diff": "@@ -1 +1 @@\n-old\n+new"}]}}})
        await self.relay.event({"id": 904, "method": "item/fileChange/requestApproval", "params": {
            "threadId": "thread", "turnId": "turn", "itemId": "edit", "grantRoot": "/fixture"}})
        prompt = self.relay.outbox()[-1][1]
        self.assertIn("/fixture/config", prompt["text"])
        self.assertIn("-old\n+new", prompt["text"])
        self.assertIn("reply_markup", prompt)

    async def test_full_outbox_blocks_new_work_but_stop_remains_available(self):
        for identifier in range(1, 129):
            await self.relay.handle(self.message(identifier, "/status"))
        self.assertEqual(len(self.relay.outbox()), 128)
        await self.relay.handle(self.message(129))
        self.assertEqual(self.worker.tasks, [])
        await self.relay.handle(self.message(130, "/stop"))
        for identifier, _ in self.relay.outbox():
            self.relay.sent(identifier)
        await self.relay.handle(self.message(131))
        self.assertEqual(self.worker.tasks, [])

    async def test_uncertain_turn_start_stops_session_and_pauses_without_replay(self):
        class UncertainWorker(Worker):
            async def begin(self, text, thread_id=None):
                await super().begin(text, thread_id)
                raise TimeoutError()
        self.relay.close()
        worker = UncertainWorker()
        self.relay = Relay(self.path, 101, 101, worker, home=Path("/home/operator"), clock=lambda: self.now)
        with self.assertRaises(RelayRejected):
            await self.relay.handle(self.message())
        self.relay.close()
        self.relay = Relay(self.path, 101, 101, worker, home=Path("/home/operator"), clock=lambda: self.now)
        await self.relay.handle(self.message(2))
        self.assertEqual(len(worker.tasks), 1)
        self.assertIn("paused", self.relay.outbox()[-1][1]["text"].lower())

    async def test_resume_queued_before_recovery_cannot_unpause_after_restart(self):
        await self.relay.handle(self.message())
        self.relay.close()
        self.now = 1005
        self.relay = Relay(self.path, 101, 101, self.worker, home=Path("/home/operator"), clock=lambda: self.now)
        await self.relay.handle(self.message(2, "/resume", date=1001))
        await self.relay.handle(self.message(3, "reboot dns", date=1005))
        self.assertEqual(len(self.worker.tasks), 1)
        self.now = 1006
        await self.relay.handle(self.message(4, "/resume", date=1006))
        await self.relay.handle(self.message(5, "Inspect current DNS state", date=1006))
        self.assertEqual(self.worker.tasks[-1], ("Inspect current DNS state", "thread"))


if __name__ == "__main__":
    unittest.main()
