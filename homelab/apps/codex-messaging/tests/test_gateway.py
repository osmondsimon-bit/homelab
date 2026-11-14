"""Verify chat authorisation and durable dispatch at the messaging boundary."""

import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.gateway import Coordinator


class RecordingWorker:
    def __init__(self):
        self.requests = []
        self.results = []

    async def begin(self, text, thread_id=None):
        self.requests.append(text)
        return "fixture-thread", "fixture-turn"

    async def interrupt(self):
        self.requests.append("interrupt")

    async def tool_result(self, event, result, *, success=True):
        self.results.append((event["id"], result, success))


class RecordingBroker:
    def __init__(self):
        self.commands = []
        self.approvals = []

    async def pause(self):
        self.commands.append("pause")

    async def resume(self):
        self.commands.append("resume")

    async def stop(self):
        self.commands.append("stop")

    async def prepare(self, user_id, chat_id, target, operation, parameters):
        return {"approval_id": "p" + "1" * 31, "plan_digest": "a" * 64, "expires_at": 1600,
                "plan": {"target_id": "guest", "operation": operation,
                         "snapshot": {"impact": ["Brief service interruption."],
                                      "verification": ["Check service health."]}}}

    async def approve(self, user_id, chat_id, approval_id, digest):
        self.approvals.append(approval_id)
        return {"job_id": "job-fixture", "state": "running"}


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.worker = RecordingWorker()
        self.broker = RecordingBroker()
        self.gateway = Coordinator(Path(self.temporary.name) / "gateway.db", 101, 101,
                                   self.worker, self.broker, clock=lambda: 1000, mode="operational")

    def tearDown(self):
        self.gateway.close()
        self.temporary.cleanup()

    def message(self, identifier=1, user=101, chat=101, text="Investigate guest", date=1000):
        return {"update_id": identifier, "message": {"from": {"id": user},
                "chat": {"id": chat, "type": "private"}, "date": date, "text": text}}

    async def test_foreign_senders_and_chats_never_reach_the_worker(self):
        await self.gateway.handle(self.message(user=202))
        await self.gateway.handle(self.message(identifier=2, chat=202))
        self.assertEqual(self.worker.requests, [])
        self.assertEqual(self.gateway.outbox(), [])

    async def test_authorised_duplicate_delivery_starts_one_durable_task(self):
        update = self.message()
        await self.gateway.handle(update)
        await self.gateway.handle(update)
        self.assertEqual(self.worker.requests, ["Investigate guest"])
        self.assertEqual(self.gateway.cursor(), 2)
        self.assertEqual(len(self.gateway.outbox()), 1)

    async def test_stale_group_and_attachment_input_never_start_work(self):
        stale = self.message(date=0)
        group = self.message(identifier=2)
        group["message"]["chat"]["type"] = "group"
        attachment = self.message(identifier=3)
        attachment["message"]["document"] = {"file_id": "fixture"}
        for update in [stale, group, attachment, self.message(identifier=4, date=2000)]:
            await self.gateway.handle(update)
        self.assertEqual(self.worker.requests, [])

    async def test_an_active_task_does_not_start_an_overlapping_turn(self):
        await self.gateway.handle(self.message())
        await self.gateway.handle(self.message(identifier=2, text="Reboot another guest"))
        self.assertEqual(self.worker.requests, ["Investigate guest"])

    async def test_retention_waits_for_idle_and_holds_uncertain_jobs(self):
        cutoffs = []
        async def prune(before):
            cutoffs.append(before)
        async def no_jobs():
            return []
        async def uncertain_job():
            return [{"state": "uncertain"}]
        self.worker.prune_inactive = prune
        self.broker.recoverable_jobs = no_jobs
        await self.gateway.handle(self.message())
        await self.gateway.maintain()
        self.assertEqual(cutoffs, [])
        await self.gateway.handle(self.message(identifier=2, text="/stop"))
        self.broker.recoverable_jobs = uncertain_job
        await self.gateway.maintain()
        self.assertEqual(cutoffs, [])
        self.broker.recoverable_jobs = no_jobs
        await self.gateway.maintain()
        self.assertEqual(cutoffs, [1000 - 30 * 86400])
        self.assertEqual(self.gateway.cursor(), 3)

    async def test_remote_diagnostic_is_delivered_after_original_job_verifies(self):
        async def diagnose(*args):
            return {"job_id": "fixture-diagnostic", "state": "running", "operation": "diagnose", "diagnostics": []}
        async def recoverable():
            return []
        async def reconcile(job_id):
            self.assertEqual(job_id, "fixture-diagnostic")
            return {"job_id": job_id, "state": "completed", "operation": "diagnose", "diagnostics": [["service_active", "yes"]]}
        self.broker.diagnose, self.broker.reconcile = diagnose, reconcile
        self.broker.recoverable_jobs = recoverable
        await self.gateway.handle(self.message())
        await self.gateway.worker_event({"id": 900, "method": "item/tool/call", "params": {
            "threadId": "fixture-thread", "turnId": "fixture-turn", "tool": "diagnose", "arguments": {"target": "guest"}}})
        self.assertEqual(self.worker.results, [])
        await self.gateway.handle(self.message(identifier=2, text="Investigate another guest"))
        self.assertEqual(self.worker.requests, ["Investigate guest"])
        await self.gateway.tick()
        self.assertEqual(self.worker.results[0][1]["diagnostics"], [["service_active", "yes"]])
        self.assertNotIn("service_active", str(self.gateway.outbox()))

    async def test_control_commands_do_not_consume_model_usage(self):
        await self.gateway.handle(self.message(text="/pause"))
        await self.gateway.handle(self.message(identifier=2, text="/status"))
        await self.gateway.handle(self.message(identifier=3, text="/resume"))
        self.assertEqual(self.worker.requests, [])
        self.assertEqual(self.broker.commands, ["pause", "resume"])

    async def test_model_proposal_cannot_dispatch_until_the_enrolled_user_approves(self):
        await self.gateway.handle(self.message(text="/resume"))
        await self.gateway.handle(self.message(identifier=2))
        event = {"id": 900, "method": "item/tool/call", "params": {"threadId": "fixture-thread",
                 "turnId": "fixture-turn", "tool": "propose_operation", "arguments": {
                     "target": "guest", "operation": "guest_reboot"}}}
        await self.gateway.worker_event(event)
        self.assertEqual(self.broker.approvals, [])
        callback = {"update_id": 3, "callback_query": {"id": "fixture-callback", "from": {"id": 202},
                    "message": {"chat": {"id": 101, "type": "private"}}, "data": "approve:p" + "1" * 31}}
        await self.gateway.handle(callback)
        self.assertEqual(self.broker.approvals, [])
        callback["update_id"] = 4
        callback["callback_query"]["from"]["id"] = 101
        await self.gateway.handle(callback)
        self.assertEqual(self.broker.approvals, ["p" + "1" * 31])
        self.assertEqual(self.worker.results[-1][0], 900)

    async def test_raw_model_diagnostics_are_not_copied_to_the_phone(self):
        await self.gateway.handle(self.message())
        await self.gateway.worker_event({"method": "item/completed", "params": {
            "threadId": "fixture-thread", "turnId": "fixture-turn",
            "item": {"type": "agentMessage", "text": json.dumps({"summary": "Connect to 192.0.2.23"})}}})
        await self.gateway.worker_event({"method": "turn/completed", "params": {"threadId": "fixture-thread", "turn": {"id": "fixture-turn", "status": "completed"}}})
        self.assertNotIn("192.0.2.23", str(self.gateway.outbox()))
        self.assertIn("Details are available locally.", self.gateway.outbox()[-1][1]["text"])

    async def test_new_does_not_abandon_an_approval_and_old_completion_does_not_unlock_a_turn(self):
        await self.gateway.handle(self.message(text="/resume"))
        await self.gateway.handle(self.message(identifier=2))
        await self.gateway.worker_event({"id": 900, "method": "item/tool/call", "params": {
            "threadId": "fixture-thread", "turnId": "fixture-turn", "tool": "propose_operation",
            "arguments": {"target": "guest", "operation": "guest_reboot"}}})
        await self.gateway.handle(self.message(identifier=3, text="/new"))
        self.assertIn("Stop an active task", self.gateway.outbox()[-1][1]["text"])
        await self.gateway.worker_event({"method": "turn/completed", "params": {
            "threadId": "old-thread", "turn": {"id": "old-turn", "status": "completed"}}})
        await self.gateway.handle(self.message(identifier=4))
        self.assertEqual(self.worker.requests, ["Investigate guest"])

    async def test_lost_dispatch_reply_is_not_permission_to_approve_again(self):
        async def lost_reply(*args):
            self.broker.approvals.append("dispatch-attempt")
            raise ConnectionError("fixture-disconnect")
        self.broker.approve = lost_reply
        await self.gateway.handle(self.message(text="/resume"))
        await self.gateway.handle(self.message(identifier=2))
        await self.gateway.worker_event({"id": 900, "method": "item/tool/call", "params": {
            "threadId": "fixture-thread", "turnId": "fixture-turn", "tool": "propose_operation",
            "arguments": {"target": "guest", "operation": "guest_reboot"}}})
        callback = {"update_id": 3, "callback_query": {"id": "fixture-callback", "from": {"id": 101},
                    "message": {"chat": {"id": 101, "type": "private"}}, "data": "approve:p" + "1" * 31}}
        await self.gateway.handle(callback)
        callback["update_id"] = 4
        await self.gateway.handle(callback)
        self.assertEqual(self.broker.approvals, ["dispatch-attempt"])
        self.assertTrue(any("uncertain" in body["text"] for _, body in self.gateway.outbox()))

    async def test_user_credential_payload_is_not_forwarded_to_the_worker(self):
        await self.gateway.handle(self.message(text="Use sk-" + "x" * 32))
        self.assertEqual(self.worker.requests, [])
        self.assertNotIn("x" * 32, str(self.gateway.outbox()))


if __name__ == "__main__":
    unittest.main()
