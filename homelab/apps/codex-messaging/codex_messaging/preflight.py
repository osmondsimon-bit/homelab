"""Inspect a pinned Codex runtime without reading operator configuration or credentials."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


EXPECTED_VERSION = "codex-cli 0.146.0"


class RuntimeRejected(Exception):
    """Expose a safe rejection code without echoing process output or credentials."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def inspect_runtime(binary: Path) -> dict:
    """Reject an unapproved runtime before any account or infrastructure authority."""
    binary = binary.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="codex-messaging-probe-") as temporary:
        root = Path(temporary)
        (root / "home").mkdir(mode=0o700)
        (root / "codex").mkdir(mode=0o700)
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root / "home"),
            "CODEX_HOME": str(root / "codex"),
            "LANG": "C.UTF-8",
        }
        result = subprocess.run(
            [str(binary), "--version"],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode or result.stdout.strip() != EXPECTED_VERSION:
            raise RuntimeRejected("runtime_version")
        schemas = root / "schema"
        generated = subprocess.run(
            [str(binary), "app-server", "generate-json-schema", "--experimental", "--out", str(schemas)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        contracts = {
            "v1/InitializeParams.json": {"clientInfo", "capabilities"},
            "v2/ThreadStartParams.json": {"permissions", "dynamicTools", "environments"},
            "v2/TurnStartParams.json": {"threadId", "input", "permissions"},
        }
        try:
            if generated.returncode:
                raise ValueError("generation")
            for name, required in contracts.items():
                schema = json.loads((schemas / name).read_text())
                if not required <= schema.get("properties", {}).keys():
                    raise ValueError("fields")
        except (OSError, ValueError, TypeError):
            raise RuntimeRejected("protocol_contract") from None
        with binary.open("rb") as executable:
            digest = hashlib.file_digest(executable, "sha256").hexdigest()
        return {"version": EXPECTED_VERSION, "sha256": digest}
