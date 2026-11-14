"""Exercise normal Codex sessions through a recording external stdio peer."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.normal_worker import NormalWorker, WorkerRejected
from codex_messaging.authentication import AuthenticationRejected


PEER = r'''
import json, os, sys
log, mode = sys.argv[1:3]
def send(value):
 print(json.dumps(value), flush=True)
def record(value):
 with open(log, 'a') as stream: stream.write(json.dumps(value)+'\n')
record({'environment':dict(os.environ), 'argv':sys.argv[3:]})
account_reads=0
approval_step=0
def prompt():
 params={
  'threadId':'thread-fixture','turnId':'turn-fixture','itemId':'command-fixture','startedAtMs':0,
  'command':'ssh fixture true','cwd':'/fixture/workspace','availableDecisions':['accept','acceptForSession','decline']}
 method='item/commandExecution/requestApproval'
 if mode=='file':
  method='item/fileChange/requestApproval'
  params={key:value for key,value in params.items() if key not in ('command','availableDecisions','cwd')}
  params['grantRoot']=None
 if mode=='permissions':
  method='item/permissions/requestApproval'
  params={key:value for key,value in params.items() if key not in ('command','availableDecisions')}
  params['permissions']={'network':{'enabled':True},'fileSystem':{'read':None,'write':['/fixture/workspace']}}
 if mode in ('question','malformed_question'):
  method='item/tool/requestUserInput'
  params={'threadId':'thread-fixture','turnId':'turn-fixture','itemId':'question-fixture','isBlocking':False,
   'questions':[{'id':'target','header':'Target','question':'Which fixture?', 'options':[{'label':'One','description':'First'},{'label':'Two','description':'Second'}]}]}
  if mode=='malformed_question': params['questions']=[None]
 if mode=='unknown': method='unsupported/request'
 if mode=='foreign': params['turnId']='other-turn'
 send({'id':'server-command','method':method,'params':params})
for line in sys.stdin:
 message=json.loads(line); record(message)
 method=message.get('method'); ident=message.get('id')
 if method is None:
  if mode in ('approval','file','permissions','question'):
   send({'method':'turn/completed','params':{'threadId':'thread-fixture','turn':{'id':'turn-fixture','status':'completed'}}})
  continue
 if method=='initialize': result={}
 elif method=='account/read':
  account_reads+=1
  result={'requiresOpenaiAuth':True, 'account':{'type':'apiKey' if mode=='wrong_auth' or mode=='rotate_auth' and account_reads>1 else 'chatgpt','planType':'plus'}}
  if mode=='malformed_account': result=None
 elif method=='account/rateLimits/read':
  result={'rateLimits':{'primary':{'usedPercent':100 if mode=='exhausted' else 1},'credits':{'hasCredits':False,'unlimited':False,'balance':'0'}}}
 elif method in ('thread/start','thread/resume'): result={'thread':{'id':'thread-fixture'},'modelProvider':'openai'}
 elif method=='turn/start':
  result={'turn':{'id':'turn-fixture','status':'inProgress'}}
 elif method=='turn/interrupt': result={}
 else: continue
 if method=='turn/start' and mode=='burst':
  for index in range(600):
   send({'method':'item/commandExecution/outputDelta','params':{'threadId':'thread-fixture','turnId':'turn-fixture','delta':'PRIVATE TOOL OUTPUT'}})
   send({'method':'item/agentMessage/delta','params':{'threadId':'thread-fixture','turnId':'turn-fixture','delta':'UNUSED DELTA'}})
 if method=='turn/start' and mode in ('burst','oversize_diff','missing_diff'):
  changes=[{'path':'/fixture/a','kind':{'type':'update','movePath':None},'diff':'PROPOSED FIXTURE DIFF'}]
  if mode=='oversize_diff': changes[0]['diff']='x'*6001
  if mode=='missing_diff': changes.append({'path':'/fixture/b','kind':{'type':'add'}})
  send({'method':'item/completed','params':{'threadId':'thread-fixture','turnId':'turn-fixture','item':{'id':'edit','type':'fileChange','changes':changes}}})
 send({'id':ident,'result':result})
 if method=='turn/interrupt':
  send({'method':'turn/completed','params':{'threadId':'thread-fixture','turn':{'id':'turn-fixture','status':'interrupted'}}})
 if method=='turn/start':
  if mode in ('approval','file','permissions','question','malformed_question','unknown','foreign'): prompt(); continue
  if mode=='output':
   send({'method':'item/commandExecution/outputDelta','params':{'threadId':'thread-fixture','turnId':'turn-fixture','delta':'PRIVATE TOOL OUTPUT'}})
   send({'method':'item/completed','params':{'threadId':'thread-fixture','turnId':'turn-fixture','item':{'id':'command','type':'commandExecution','command':'fixture','aggregatedOutput':'PRIVATE TOOL OUTPUT'}}})
   send({'method':'item/completed','params':{'threadId':'other-thread','turnId':'turn-fixture','item':{'id':'answer','type':'agentMessage','text':'WRONG THREAD'}}})
  send({'method':'item/completed','params':{'threadId':'thread-fixture','turnId':'turn-fixture','item':{'id':'answer','type':'agentMessage','text':'Fixture ready.'}}})
  send({'method':'turn/completed','params':{'threadId':'thread-fixture','turn':{'id':'turn-fixture','status':'completed'}}})
'''


class NormalWorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.context, self.workspace = self.root / "home", self.root / "workspace"
        (self.context / ".codex").mkdir(parents=True)
        self.workspace.mkdir()
        self.settings = self.context / ".codex/config.toml"
        self.settings.write_text('[features]\nshell_tool = true\n')
        self.peer = self.root / "peer.py"
        self.peer.write_text(PEER)
        self.log = self.root / "wire.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def worker(self, mode="normal"):
        return NormalWorker([sys.executable, str(self.peer), str(self.log), mode], self.context, self.workspace,
            inherited={"PATH":"/usr/bin:/bin", "SSH_AUTH_SOCK":"/fixture/ssh-agent",
                       "OPENAI_API_KEY":"DUMMY-API-KEY", "OPENAI_BASE_URL":"https://invalid.fixture",
                       "FIXTURE_API_KEY":"DUMMY-NATIVE-TOOL-KEY", "FIXTURE_BASE_URL":"https://native.fixture"})

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    async def test_normal_session_inherits_user_tools_and_ssh_without_custom_sandbox(self):
        async with self.worker() as worker:
            self.assertEqual(await worker.begin("Inspect the fixture."), ("thread-fixture", "turn-fixture"))
            event = await asyncio.wait_for(worker.next_event(), 2)
            self.assertEqual(event["params"]["item"]["text"], "Fixture ready.")
        records = self.records()
        environment, argv = records[0]["environment"], records[0]["argv"]
        self.assertEqual(environment["PATH"], "/usr/bin:/bin")
        self.assertEqual(environment["SSH_AUTH_SOCK"], "/fixture/ssh-agent")
        self.assertEqual(environment["HOME"], str(self.context))
        self.assertEqual(environment["CODEX_HOME"], str(self.context / ".codex"))
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("OPENAI_BASE_URL", environment)
        self.assertEqual(environment["FIXTURE_API_KEY"], "DUMMY-NATIVE-TOOL-KEY")
        self.assertEqual(environment["FIXTURE_BASE_URL"], "https://native.fixture")
        self.assertIn('forced_login_method="chatgpt"', argv)
        self.assertIn('model_provider="openai"', argv)
        self.assertEqual(argv[-3:], ["app-server", "--listen", "stdio://"])
        for record in records:
            if record.get("method") in {"thread/start", "turn/start"}:
                self.assertFalse({"environments", "dynamicTools", "permissions", "sandbox", "approvalPolicy"} & record["params"].keys())
        self.assertEqual(self.settings.read_text(), '[features]\nshell_tool = true\n')

    async def test_custom_absolute_codex_home_is_preserved_and_relative_home_rejected(self):
        alternate = str(self.root / "existing-custom-config")
        async with NormalWorker([sys.executable, str(self.peer), str(self.log), "normal"],
                self.context, self.workspace, inherited={"PATH":"/usr/bin:/bin", "CODEX_HOME":alternate}):
            pass
        self.assertEqual(self.records()[0]["environment"]["CODEX_HOME"], alternate)
        with self.assertRaises(WorkerRejected):
            NormalWorker([sys.executable], self.context, self.workspace, inherited={"CODEX_HOME":"relative"})

    async def test_subscription_is_rechecked_before_every_turn(self):
        async with self.worker("rotate_auth") as worker:
            await worker.begin("First task.")
            await worker.next_event()
            completed = await worker.next_event()
            self.assertEqual(completed["method"], "turn/completed")
            with self.assertRaises(AuthenticationRejected):
                await worker.begin("Must not reach a model.", "thread-fixture")
        self.assertEqual(sum(record.get("method") == "turn/start" for record in self.records()), 1)

    async def test_wrong_auth_and_exhausted_allowance_never_start_model_work(self):
        for mode in ("wrong_auth", "exhausted"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                async with self.worker(mode) as worker:
                    with self.assertRaises(AuthenticationRejected):
                        await worker.begin("Must not reach a model.")
                self.assertFalse(any(record.get("method") in {"thread/start", "thread/resume", "turn/start"}
                                     for record in self.records()))
                if mode == "wrong_auth":
                    self.assertFalse(any(record.get("method") == "account/rateLimits/read" for record in self.records()))

    async def test_command_approval_is_correlated_immutable_and_single_use(self):
        async with self.worker("approval") as worker:
            await worker.begin("Run the fixture command.")
            approval = await worker.next_event()
            changed = json.loads(json.dumps(approval))
            changed["params"]["command"] = "unexpected command"
            with self.assertRaises(WorkerRejected):
                await worker.approve(changed, True)
            await worker.approve(approval, True)
            with self.assertRaises(WorkerRejected):
                await worker.approve(approval, True)
            self.assertEqual((await worker.next_event())["method"], "turn/completed")
        reply = [record for record in self.records() if record.get("id") == "server-command"][-1]
        self.assertEqual(reply, {"id":"server-command", "result":{"decision":"accept"}})

    async def test_file_and_permission_responses_never_grant_session_scope(self):
        for mode in ("file", "permissions"):
            for accepted in (False, True):
                with self.subTest(mode=mode, accepted=accepted):
                    self.log.unlink(missing_ok=True)
                    async with self.worker(mode) as worker:
                        await worker.begin("Review the requested fixture scope.")
                        event = await worker.next_event()
                        await worker.approve(event, accepted)
                        await worker.next_event()
                    reply = [record for record in self.records() if record.get("id") == "server-command"][-1]
                    if mode == "file":
                        self.assertEqual(reply["result"], {"decision":"accept" if accepted else "decline"})
                    else:
                        self.assertEqual(reply["result"], {"scope":"turn", "permissions":event["params"]["permissions"] if accepted else {}})

    async def test_question_answers_are_bound_to_the_exact_pending_request(self):
        async with self.worker("question") as worker:
            await worker.begin("Ask the fixture question.")
            event = await worker.next_event()
            with self.assertRaises(WorkerRejected):
                await worker.answer_question(event, {"unrequested":{"answers":["Two"]}})
            answers = {"target":{"answers":["Two"]}}
            await worker.answer_question(event, answers)
            with self.assertRaises(WorkerRejected):
                await worker.answer_question(event, answers)
            await worker.next_event()
        reply = [record for record in self.records() if record.get("id") == "server-command"][-1]
        self.assertEqual(reply["result"], {"answers":answers})

    async def test_question_cancellation_consumes_only_the_original_request(self):
        async with self.worker("question") as worker:
            await worker.begin("Ask the fixture question.")
            event = await worker.next_event()
            changed = json.loads(json.dumps(event))
            changed["params"]["turnId"] = "other-turn"
            with self.assertRaises(WorkerRejected):
                await worker.cancel_question(changed)
            await worker.cancel_question(event)
            with self.assertRaises(WorkerRejected):
                await worker.cancel_question(event)
            self.assertEqual((await worker.next_event())["method"], "turn/completed")
        reply = [record for record in self.records() if record.get("id") == "server-command"][-1]
        self.assertEqual(reply["result"], {"answers":{}})

    async def test_interrupt_invalidates_outstanding_approval_and_uses_original_turn(self):
        async with self.worker("approval") as worker:
            await worker.begin("Run the fixture command.")
            event = await worker.next_event()
            await worker.interrupt()
            with self.assertRaises(WorkerRejected):
                await worker.approve(event, True)
            self.assertEqual((await worker.next_event())["params"]["turn"]["status"], "interrupted")
        calls = [record for record in self.records() if record.get("method") == "turn/interrupt"]
        self.assertEqual(calls[0]["params"], {"threadId":"thread-fixture", "turnId":"turn-fixture"})

    async def test_interrupt_cannot_admit_an_already_queued_new_approval(self):
        async with self.worker("approval") as worker:
            await worker.begin("Run the fixture command.")
            await worker.interrupt()
            with self.assertRaises(WorkerRejected) as rejected:
                await worker.next_event()
            self.assertEqual(rejected.exception.code, "worker_request_not_allowed")

    async def test_unknown_or_other_turn_request_is_denied_without_payload_echo(self):
        for mode in ("unknown", "foreign"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                async with self.worker(mode) as worker:
                    await worker.begin("Run the fixture command.")
                    with self.assertRaises(WorkerRejected) as rejected:
                        await worker.next_event()
                    self.assertEqual(rejected.exception.code, "worker_request_not_allowed")
                reply = [record for record in self.records() if record.get("id") == "server-command"][-1]
                self.assertEqual(reply["error"], {"code":-32601, "message":"request not supported"})

    async def test_native_output_and_unrelated_notifications_are_not_relayed(self):
        async with self.worker("output") as worker:
            await worker.begin("Inspect the fixture.")
            metadata = await worker.next_event()
            self.assertEqual(metadata["params"]["item"], {"id":"command", "type":"commandExecution", "command":"fixture"})
            answer = await worker.next_event()
            self.assertEqual(answer["params"]["item"]["text"], "Fixture ready.")
            self.assertNotIn("PRIVATE TOOL OUTPUT", json.dumps([metadata, answer]))

    async def test_output_burst_is_discarded_before_queue_but_full_approval_diff_is_preserved(self):
        async with self.worker("burst") as worker:
            await asyncio.wait_for(worker.begin("Inspect the fixture."), 2)
            metadata = await asyncio.wait_for(worker.next_event(), 2)
            self.assertEqual(metadata["params"]["item"]["changes"],
                [{"path":"/fixture/a", "kind":{"type":"update", "movePath":None}, "diff":"PROPOSED FIXTURE DIFF"}])
            self.assertTrue(metadata["params"]["item"]["diffAvailable"])
            answer = await asyncio.wait_for(worker.next_event(), 2)
            self.assertEqual(answer["params"]["item"]["text"], "Fixture ready.")
            self.assertEqual((await worker.next_event())["method"], "turn/completed")
            self.assertNotIn("PRIVATE", json.dumps([metadata, answer]))

    async def test_missing_or_oversize_file_diffs_never_forward_partial_scope(self):
        for mode in ("oversize_diff", "missing_diff"):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                async with self.worker(mode) as worker:
                    await worker.begin("Inspect the fixture patch.")
                    item = (await worker.next_event())["params"]["item"]
                    self.assertFalse(item["diffAvailable"])
                    self.assertTrue(all("diff" not in change for change in item["changes"]))

    async def test_phone_guidance_is_fixed_on_new_and_resumed_threads(self):
        async with self.worker() as worker:
            await worker.begin("First task.")
            await worker.next_event()
            await worker.next_event()
            await worker.begin("Second task.", "thread-fixture")
        calls = [record for record in self.records() if record.get("method") in {"thread/start", "thread/resume"}]
        guidance = [call["params"]["developerInstructions"] for call in calls]
        self.assertEqual(guidance[0], guidance[1])
        self.assertIn("AGENTS.md", guidance[0])
        self.assertIn("usual approvals", guidance[0])
        self.assertIn("uncertain", guidance[0])
        self.assertIn("relay state", guidance[0])

    async def test_simultaneous_begin_cannot_create_two_model_turns(self):
        async with self.worker() as worker:
            results = await asyncio.gather(worker.begin("First"), worker.begin("Second"), return_exceptions=True)
            self.assertEqual(sum(isinstance(result, WorkerRejected) for result in results), 1)
        self.assertEqual(sum(record.get("method") == "turn/start" for record in self.records()), 1)

    async def test_malformed_upstream_fields_expose_only_safe_errors(self):
        async with self.worker("malformed_account") as worker:
            with self.assertRaises(WorkerRejected) as rejected:
                await worker.begin("Must not start model work.")
            self.assertEqual(rejected.exception.code, "worker_protocol")
        self.log.unlink()
        async with self.worker("malformed_question") as worker:
            await worker.begin("Ask the fixture question.")
            event = await worker.next_event()
            with self.assertRaises(WorkerRejected) as rejected:
                await worker.answer_question(event, {})
            self.assertEqual(rejected.exception.code, "question_answers_invalid")
