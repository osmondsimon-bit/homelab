"""Run the actual app-server with synthetic credentials and a local scripted model."""

import http.server
import json
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_messaging.worker_policy import feature_configuration, thread_parameters

def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def run_fixture(binary: Path, *, native_environment=False) -> dict:
    """Require a genuine native command result and dynamic-tool exchange, not a model refusal."""
    # /tmp may contain an unrelated .codex layer; never trust it to make a fixture pass.
    with tempfile.TemporaryDirectory(prefix="codex-messaging-native-", dir="/var/tmp") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        context = root / "codex"
        for directory in [workspace, context, root / "home"]:
            directory.mkdir(mode=0o700)
        runtime = root / "runtime"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "codex-resources").mkdir()
        source_binary = binary.resolve(strict=True)
        fixture_binary = runtime / "bin" / "codex"
        shutil.copy2(source_binary, fixture_binary)
        shutil.copy2(source_binary.parent.parent / "codex-resources" / "bwrap",
                     runtime / "codex-resources" / "bwrap")
        (workspace / "reference.txt").write_text("PUBLIC-REFERENCE")
        (context / "auth.json").write_text('{"OPENAI_API_KEY":null}')
        (context / "credential-sentinel").write_text("DUMMY-CREDENTIAL-NOT-A-REAL-TOKEN")
        skill = context / "skills" / "safe-fixture"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: safe-fixture\ndescription: Read-only keyless test reference.\n---\nPurpose: provide PUBLIC-SKILL-REFERENCE for the keyless fixture.\n")
        requests = []
        handler_errors = []
        model_tools = []
        outputs = []
        native_outputs = []
        tool_results = {}
        calls = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 4_000_000 or self.headers.get("Content-Encoding"):
                        raise RuntimeError("unsupported fixture request encoding")
                    payload = json.loads(self.rfile.read(length))
                    requests.append(payload)
                    outputs.extend(_strings(payload.get("input", [])))
                    for item in payload.get("input", []):
                        if isinstance(item, dict) and item.get("type") == "function_call_output" and item.get("call_id") == "fixture-native":
                            native_outputs.append(item.get("output"))
                        if isinstance(item, dict) and item.get("type") == "function_call_output":
                            tool_results[item.get("call_id")] = item.get("output")
                    tools = {}
                    for entry in payload.get("tools", []):
                        if entry.get("type") == "function":
                            tools[entry["name"]] = None
                        elif entry.get("type") == "namespace":
                            for tool in entry.get("tools", []):
                                tools[tool["name"]] = entry["name"]
                    model_tools[:] = sorted(f"{namespace}.{name}" if namespace else name for name, namespace in tools.items())
                    ordinal = len(requests)
                    if ordinal == 1:
                        name = next((name for name in ["exec_command", "shell_command", "shell"] if name in tools), None)
                        if name is None and native_environment:
                            raise RuntimeError("no native shell tool in fixture model contract: " + ",".join(model_tools))
                        name = name or "exec_command"
                        command = shlex.join([sys.executable, str(workspace / "probe.py")])
                        arguments = {"cmd": command} if name == "exec_command" else {"command": command}
                        if name == "shell":
                            arguments = {"command": ["/bin/sh", "-c", command]}
                        item = {"type": "function_call", "name": name, "arguments": json.dumps(arguments), "call_id": "fixture-native"}
                        if tools.get(name):
                            item["namespace"] = tools[name]
                    elif not native_environment and ordinal == 2:
                        item = {"type": "function_call", "name": "view_image", "arguments": json.dumps({"path": str(context / "auth.json")}), "call_id": "fixture-image"}
                    elif not native_environment and ordinal == 3:
                        item = {"type": "function_call", "name": "spawn_agent", "arguments": json.dumps({"message": "Return only fixture status.", "agent_type": "default"}), "call_id": "fixture-agent"}
                    elif not native_environment and ordinal == 4:
                        item = {"type": "function_call", "namespace": "skills", "name": "list", "arguments": json.dumps({"authority": {"kind": "orchestrator"}}), "call_id": "fixture-skillslist"}
                    elif not native_environment and ordinal == 5:
                        item = {"type": "function_call", "namespace": "skills", "name": "list", "arguments": json.dumps({"authority": {"kind": "executor"}}), "call_id": "fixture-executorskillslist"}
                    elif not native_environment and ordinal == 6:
                        item = {"type": "function_call", "namespace": "skills", "name": "read", "arguments": json.dumps({"authority": {"kind": "orchestrator"}, "package": "skill://fixture/reference", "resource": "file://" + str(context / "credential-sentinel")}), "call_id": "fixture-orchestratorread"}
                    elif not native_environment and ordinal == 7:
                        item = {"type": "function_call", "namespace": "skills", "name": "read", "arguments": json.dumps({"authority": {"kind": "executor", "id": "fixture"}, "package": str(skill), "resource": "../../credential-sentinel"}), "call_id": "fixture-executorread"}
                    elif ordinal == (2 if native_environment else 8):
                        item = {"type": "function_call", "name": "fixture_diagnostic", "arguments": "{}", "call_id": "fixture-dynamic"}
                        if tools.get("fixture_diagnostic"):
                            item["namespace"] = tools["fixture_diagnostic"]
                    elif ordinal == (3 if native_environment else 9):
                        item = {"type": "message", "id": "fixture-message", "role": "assistant", "content": [{"type": "output_text", "text": "Fixture complete."}]}
                    else:
                        raise RuntimeError("unexpected additional model request")
                    events = [
                        {"type": "response.created", "response": {"id": f"fixture-{ordinal}"}},
                        {"type": "response.output_item.done", "output_index": 0, "item": item},
                        {"type": "response.completed", "response": {"id": f"fixture-{ordinal}", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}},
                    ]
                    body = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as error:
                    handler_errors.append(str(error))
                    self.send_error(500)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        probe = f'''"""Probe only synthetic data through the real model-controlled command tool."""
import errno, json, socket
from pathlib import Path
result = {{}}
result["reference_read"] = "allowed" if Path("reference.txt").read_text() == "PUBLIC-REFERENCE" else "wrong"
for name, path in [("credential_read", {str(context / 'credential-sentinel')!r}), ("auth_file", {str(context / 'auth.json')!r}), ("process_environment", "/proc/self/environ")]:
    try:
        Path(path).read_bytes()
        result[name] = "exposed"
    except (PermissionError, FileNotFoundError):
        result[name] = "denied"
try:
    with socket.socket() as connection:
        connection.settimeout(2)
        outcome = connection.connect_ex(("127.0.0.1", {port}))
        result["direct_network"] = "denied" if outcome in {{errno.EPERM, errno.EACCES}} else "exposed" if outcome == 0 else "inconclusive"
except PermissionError:
    result["direct_network"] = "denied"
print("MESSAGING_PROBE=" + json.dumps(result, sort_keys=True))
'''
        (workspace / "probe.py").write_text(probe)
        (context / "config.toml").write_text(
            'model = "fixture"\nmodel_provider = "fixture"\nweb_search = "disabled"\n'
            'default_permissions = "messaging"\napproval_policy = "never"\n'
            + ('[features]\nshell_tool = true\nunified_exec = true\napps = false\n' if native_environment else feature_configuration())
            +
            '[model_providers.fixture]\nname = "Local fixture"\nwire_api = "responses"\n'
            f'base_url = "http://127.0.0.1:{port}/v1"\n'
            'requires_openai_auth = false\nsupports_websockets = false\nrequest_max_retries = 0\nstream_max_retries = 0\n'
            '[permissions.messaging.filesystem]\n":root" = "read"\n'
            f'{json.dumps(str(context))} = "deny"\n"/proc" = "deny"\n"/home" = "deny"\n'
            '[permissions.messaging.network]\nenabled = false\n'
        )
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(root / "home"),
                       "CODEX_HOME": str(context), "LANG": "C.UTF-8"}
        guard = Path(__file__).with_name("fixture_network_guard.py")
        process = subprocess.Popen(
            [sys.executable, str(guard), str(port), str(fixture_binary), "--strict-config", "app-server", "--listen", "stdio://"],
            cwd=workspace, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        incoming = queue.Queue()
        errors = []

        def read_output():
            for line in process.stdout:
                try:
                    incoming.put(json.loads(line))
                except ValueError:
                    incoming.put({"fixture_error": "non-JSON app-server output"})
            incoming.put({"fixture_error": "app-server ended before completion"})

        def read_errors():
            for line in process.stderr:
                errors.append(line)

        reader = threading.Thread(target=read_output, daemon=True)
        error_reader = threading.Thread(target=read_errors, daemon=True)
        reader.start()
        error_reader.start()

        def send(value):
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()

        def receive():
            try:
                message = incoming.get(timeout=25)
            except queue.Empty:
                raise RuntimeError("app-server fixture timed out") from None
            if "fixture_error" in message:
                raise RuntimeError(message["fixture_error"] + ": " + "".join(errors)[-2000:])
            return message

        def request(identifier, method, params):
            send({"id": identifier, "method": method, "params": params})
            while True:
                message = receive()
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError("fixture RPC rejected: " + method + ": " + json.dumps(message["error"]))
                    return message["result"]

        try:
            request(1, "initialize", {"clientInfo": {"name": "messaging-keyless-fixture", "version": "1"}, "capabilities": {"experimentalApi": True}})
            send({"method": "initialized"})
            tools = [{"type": "function", "name": "fixture_diagnostic", "description": "Return only a synthetic diagnostic receipt.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}]
            parameters = thread_parameters(str(workspace), tools)
            if native_environment:
                parameters.pop("environments")
            thread = request(2, "thread/start", parameters)
            request(3, "turn/start", {"threadId": thread["thread"]["id"], "input": [{"type": "text", "text": "Run the synthetic fixture."}]})
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                message = receive()
                if message.get("method") == "item/tool/call":
                    if message["params"]["tool"] != "fixture_diagnostic":
                        raise RuntimeError("unexpected dynamic tool")
                    calls.append("fixture_diagnostic")
                    send({"id": message["id"], "result": {"success": True, "contentItems": [{"type": "inputText", "text": "FIXTURE_DYNAMIC_OK"}]}})
                elif message.get("method") == "turn/completed":
                    if message["params"]["turn"]["status"] != "completed":
                        detail = handler_errors[0] if handler_errors else f"requests={len(requests)}; tools={','.join(model_tools)}"
                        raise RuntimeError("fixture turn did not complete: " + detail + "; " + json.dumps(message["params"]["turn"].get("error")))
                    break
            else:
                raise RuntimeError("fixture deadline exceeded")
            if handler_errors:
                raise RuntimeError("fixture model error: " + handler_errors[0])
            dynamic = "completed" if calls and any("FIXTURE_DYNAMIC_OK" in value for value in outputs) else "missing"
            if not native_environment:
                report = {"dynamic_tool": dynamic}
                for name, identifier in [("native_shell", "fixture-native"), ("native_image", "fixture-image"), ("native_agent", "fixture-agent")]:
                    outcome = str(tool_results.get(identifier, ""))
                    report[name] = "unavailable" if "unsupported" in outcome.lower() or "unrecognized function" in outcome.lower() or "unknown function" in outcome.lower() else outcome[:500]
                report["advertised_tools"] = model_tools
                report["skills_listing"] = tool_results.get("fixture-skillslist", "missing")
                report["executor_skills_listing"] = tool_results.get("fixture-executorskillslist", "missing")
                report["orchestrator_read"] = tool_results.get("fixture-orchestratorread", "missing")
                report["executor_read"] = tool_results.get("fixture-executorread", "missing")
                report["resource_tools"] = [entry for entry in requests[0].get("tools", [])
                                            if any(name in {"list", "read"} for name in _strings(entry.get("name", "")))
                                            or entry.get("type") == "namespace" and any(tool.get("name") in {"list", "read"} for tool in entry.get("tools", []))]
                return report
            for output in outputs:
                marker = output.find("MESSAGING_PROBE=")
                if marker != -1:
                    report, _ = json.JSONDecoder().raw_decode(output[marker + len("MESSAGING_PROBE="):])
                    report["dynamic_tool"] = dynamic
                    return report
            raise RuntimeError("native probe never completed; tools=" + ",".join(model_tools)
                               + "; fixture outputs=" + repr(native_outputs)[:1800])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=2)
            error_reader.join(timeout=2)
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
            server.shutdown()
            server.server_close()
            serving.join(timeout=2)
