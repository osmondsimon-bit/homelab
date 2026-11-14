"""Verify worker protocol and subscription gates against an external fake peer."""

import json
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.authentication import AuthenticationRejected
from codex_messaging.rpc import RpcWorker


class WorkerProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_account_never_receives_a_model_turn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "model-turn"
            peer = root / "peer.py"
            peer.write_text('''"""Serve a keyless protocol peer for the account gate test."""
import json, sys
from pathlib import Path
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    method = request["method"]
    result = {}
    if method == "account/read":
        result = {"requiresOpenaiAuth": True, "account": {"type": "apiKey"}}
    if method == "turn/start":
        Path(''' + repr(str(marker)) + ''').write_text("unexpected")
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
''')
            async with RpcWorker([sys.executable, str(peer)], root, root, inherited={}) as worker:
                with self.assertRaises(AuthenticationRejected):
                    await worker.begin("Investigate guest")
            self.assertFalse(marker.exists())

    async def test_subscription_turn_uses_the_restricted_surface_and_correlated_tool_reply(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = root / "receipt.json"
            peer = root / "peer.py"
            peer.write_text('''"""Serve a subscription-backed-looking peer without any network access."""
import json, sys
from pathlib import Path
for line in sys.stdin:
    request = json.loads(line)
    if "method" not in request:
        if request.get("id") == 900:
            Path(''' + repr(str(receipt)) + ''').write_text(json.dumps(request["result"]))
        continue
    if "id" not in request:
        continue
    method = request["method"]
    result = {}
    if method == "account/read":
        result = {"requiresOpenaiAuth": True, "account": {"type": "chatgpt", "planType": "plus"}}
    elif method == "account/rateLimits/read":
        result = {"rateLimits": {"primary": {"usedPercent": 10}, "credits": {"hasCredits": False, "unlimited": False, "balance": "0"}}}
    elif method == "thread/start":
        assert request["params"]["environments"] == []
        assert request["params"]["permissions"] == "messaging"
        assert {tool["name"] for tool in request["params"]["dynamicTools"]} == {"diagnose", "propose_operation"}
        result = {"thread": {"id": "fixture-thread"}}
    elif method == "turn/start":
        result = {"turn": {"id": "fixture-turn"}}
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if method == "turn/start":
        print(json.dumps({"id":900,"method":"item/tool/call","params":{"threadId":"fixture-thread","turnId":"fixture-turn","tool":"diagnose","callId":"fixture-call","arguments":{"target":"guest"}}}),flush=True)
''')
            async with RpcWorker([sys.executable, str(peer)], root, root, inherited={}) as worker:
                identifiers = await worker.begin("Investigate guest")
                self.assertEqual(identifiers, ("fixture-thread", "fixture-turn"))
                event = await worker.next_event()
                await worker.tool_result(event, {"state": "healthy"})
                await worker.interrupt()
            self.assertTrue(json.loads(receipt.read_text())["success"])

    async def test_worker_exit_is_reported_instead_of_leaving_a_task_hanging(self):
        from codex_messaging.rpc import WorkerRejected
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            peer = root / "peer.py"
            peer.write_text('''"""Complete initialisation and disconnect without model activity."""
import json,sys
request=json.loads(sys.stdin.readline())
print(json.dumps({"id":request["id"],"result":{}}),flush=True)
sys.stdin.readline()
''')
            async with RpcWorker([sys.executable, str(peer)], root, root, inherited={}) as worker:
                with self.assertRaises(WorkerRejected):
                    await asyncio.wait_for(worker.next_event(), timeout=1)

    async def test_retention_removes_only_expired_inactive_own_workspace_threads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            deleted = root / "deleted.json"
            peer = root / "peer.py"
            peer.write_text('''"""Expose only local thread metadata to the retention test."""
import json,sys
from pathlib import Path
removed=[]
for line in sys.stdin:
    request=json.loads(line)
    if "id" not in request: continue
    result={}
    if request["method"]=="thread/list":
        result={"nextCursor":None,"data": [] if request["params"]["archived"] else [
            {"id":"00000000-0000-7000-8000-000000000001","cwd":''' + repr(str(root)) + ''',"updatedAt":100,"status":{"type":"idle"}},
            {"id":"00000000-0000-7000-8000-000000000002","cwd":''' + repr(str(root)) + ''',"updatedAt":100,"status":{"type":"active","activeFlags":[]}},
            {"id":"00000000-0000-7000-8000-000000000003","cwd":''' + repr(str(root)) + ''',"updatedAt":900,"status":{"type":"idle"}},
            {"id":"00000000-0000-7000-8000-000000000004","cwd":"/fixture/other","updatedAt":100,"status":{"type":"idle"}}]}
    if request["method"]=="thread/delete":
        removed.append(request["params"]["threadId"])
        Path(''' + repr(str(deleted)) + ''').write_text(json.dumps(removed))
    print(json.dumps({"id":request["id"],"result":result}),flush=True)
''')
            async with RpcWorker([sys.executable, str(peer)], root, root, inherited={}) as worker:
                count = await worker.prune_inactive(500)
            self.assertEqual(count, 1)
            self.assertEqual(json.loads(deleted.read_text()), ["00000000-0000-7000-8000-000000000001"])


if __name__ == "__main__":
    unittest.main()
