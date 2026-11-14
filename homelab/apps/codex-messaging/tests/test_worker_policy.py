"""Reject effective runtime feature drift before the worker starts serving turns."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_messaging.worker_policy import DISABLED_FEATURES, verify_features


class FeaturePolicyTests(unittest.TestCase):
    def test_enabled_or_missing_restricted_features_cannot_pass_the_gate(self):
        baseline = "\n".join(f"{name} stable false" for name in DISABLED_FEATURES)
        verify_features(baseline)
        for changed in [baseline.replace("shell_tool stable false", "shell_tool stable true"), ""]:
            with self.subTest(changed=bool(changed)), self.assertRaises(ValueError):
                verify_features(changed)


if __name__ == "__main__":
    unittest.main()
