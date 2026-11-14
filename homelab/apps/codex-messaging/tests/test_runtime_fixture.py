"""Exercise the real pinned app-server against a keyless local model fixture."""

import os
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_fixture import run_fixture


@unittest.skipUnless(os.environ.get("CODEX_MESSAGING_TEST_BINARY"), "explicit pinned runtime required")
class RealRuntimeTests(unittest.TestCase):
    def test_forbidden_native_functions_cannot_run_while_dynamic_tools_work(self):
        report = run_fixture(Path(os.environ["CODEX_MESSAGING_TEST_BINARY"]), native_environment=False)
        self.assertEqual(report["native_shell"], "unavailable")
        self.assertEqual(report["native_image"], "unavailable")
        self.assertEqual(report["native_agent"], "unavailable")
        self.assertEqual(report["dynamic_tool"], "completed")
        self.assertEqual(set(report["advertised_tools"]), {
            "fixture_diagnostic", "request_user_input", "update_plan", "skills.list", "skills.read",
        }, repr(report["resource_tools"]))
        self.assertEqual(json.loads(report["skills_listing"])["skills"], [])
        self.assertEqual(json.loads(report["executor_skills_listing"])["skills"], [])
        self.assertEqual(report["orchestrator_read"], "skill package is not available from the requested authority")
        self.assertEqual(report["executor_read"], "skill package is not available from the requested authority")


if __name__ == "__main__":
    unittest.main()
