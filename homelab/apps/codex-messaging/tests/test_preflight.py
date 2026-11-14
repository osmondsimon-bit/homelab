"""Verify the keyless runtime gate through its public inspection interface."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.preflight import RuntimeRejected, inspect_runtime


class RuntimeGateTests(unittest.TestCase):
    def test_an_unapproved_runtime_cannot_pass_the_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "unapproved codex"
            binary.write_text("#!/bin/sh\nprintf 'codex-cli 0.147.0\\n'\n")
            binary.chmod(0o700)
            with self.assertRaises(RuntimeRejected) as rejected:
                inspect_runtime(binary)
            self.assertEqual(rejected.exception.code, "runtime_version")

    def test_a_version_label_without_the_required_protocol_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "incomplete-codex"
            binary.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = --version ]; then printf 'codex-cli 0.146.0\\n'; fi\n"
            )
            binary.chmod(0o700)
            with self.assertRaises(RuntimeRejected) as rejected:
                inspect_runtime(binary)
            self.assertEqual(rejected.exception.code, "protocol_contract")


if __name__ == "__main__":
    unittest.main()
