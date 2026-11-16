#!/usr/bin/env python3
"""Exercise the independent Oneill watchdog's outage, delivery and recovery behavior."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "homelab/ansible/files/monitoring/oneill-watch.sh"


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            STATE_DIR=str(self.root / "state"),
            TEXTFILE_DIR=str(self.root / "metrics"),
            NTFY_URL="https://ntfy.invalid/private-test-topic",
            MONITORING_URL="http://monitoring.invalid:9090/-/healthy",
            DNS_IP="192.0.2.53",
            CALL_LOG=str(self.log),
        )
        self.stub("curl", '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
publish = "--config" in args
config = sys.stdin.read() if publish else ""
with open(os.environ["CALL_LOG"], "a") as f:
    f.write(json.dumps({"args": args, "publish": publish, "config": config}) + "\\n")
if publish:
    failed = os.environ.get("PUBLISH_FAIL") == "1"
    if "--doh-url" in args and os.environ.get("DOH_SUCCESS") == "1":
        failed = False
else:
    failed = os.environ.get("PROBE_FAIL") == "1"
if failed:
    print("curl failure: " + os.environ["NTFY_URL"], file=sys.stderr)
sys.exit(7 if failed else 0)
''')
        self.stub("timeout", '''#!/usr/bin/env python3
import os, sys
sys.exit(1 if os.environ.get("DNS_FAIL") == "1" else 0)
''')

    def stub(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def run_watch(self, expected=0, **changes):
        self.assertTrue(SCRIPT.exists(), "independent watchdog implementation is missing")
        self.env.update(changes)
        result = subprocess.run(
            ["bash", str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertNotIn("private-test-topic", result.stdout + result.stderr)
        return result

    def publishes(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()
                if json.loads(x)["publish"]] if self.log.exists() else []

    def metrics(self):
        return (self.root / "metrics/homelab_oneill_watch.prom").read_text()

    def test_healthy_is_silent_and_emits_heartbeat(self):
        self.run_watch()
        self.assertEqual(self.publishes(), [])
        self.assertIn('homelab_oneill_watch_probe_success{node="apophis"} 1', self.metrics())
        self.assertIn('homelab_oneill_watch_last_check_timestamp_seconds{node="apophis"}', self.metrics())

    def test_outage_is_urgent_deduplicated_and_recovers_once(self):
        self.run_watch(PROBE_FAIL="1", DNS_FAIL="1")
        calls = self.publishes()
        self.assertEqual(len(calls), 1)
        self.assertIn("Priority: urgent", calls[0]["args"])
        self.assertIn("monitoring", " ".join(calls[0]["args"]))
        self.assertIn("DNS", " ".join(calls[0]["args"]))
        self.run_watch()
        self.assertEqual(len(self.publishes()), 1)
        self.run_watch(PROBE_FAIL="0", DNS_FAIL="0")
        self.assertEqual(len(self.publishes()), 2)
        self.assertIn("recovered", " ".join(self.publishes()[-1]["args"]).lower())
        self.run_watch()
        self.assertEqual(len(self.publishes()), 2)

    def test_reminds_after_thirty_minutes(self):
        self.run_watch(PROBE_FAIL="1")
        (self.root / "state/last-notified").write_text(str(int(time.time()) - 1801))
        self.run_watch()
        self.assertEqual(len(self.publishes()), 2)

    def test_changed_failure_is_reported(self):
        self.run_watch(PROBE_FAIL="1")
        self.run_watch(DNS_FAIL="1")
        self.assertEqual(len(self.publishes()), 2)

    def test_failed_delivery_is_visible_and_retried(self):
        result = self.run_watch(expected=1, PROBE_FAIL="1", PUBLISH_FAIL="1")
        self.assertIn("delivery failed", result.stderr)
        self.assertIn('homelab_oneill_watch_delivery_success{node="apophis"} 0', self.metrics())
        self.assertEqual(len(self.publishes()), 2)
        self.run_watch(PUBLISH_FAIL="0")
        self.assertEqual(len(self.publishes()), 3)
        self.assertIn('homelab_oneill_watch_delivery_success{node="apophis"} 1', self.metrics())

    def test_doh_recovers_from_local_dns_failure_with_verified_tls(self):
        self.run_watch(PROBE_FAIL="1", PUBLISH_FAIL="1", DOH_SUCCESS="1")
        calls = self.publishes()
        self.assertEqual(len(calls), 2)
        self.assertIn("--doh-url", calls[1]["args"])
        self.assertIn("https://1.1.1.1/dns-query", calls[1]["args"])
        for call in calls:
            self.assertIn("--connect-timeout", call["args"])
            self.assertIn("--max-time", call["args"])
            self.assertNotIn("--insecure", call["args"])
            self.assertNotIn("--doh-insecure", call["args"])
            self.assertNotIn(self.env["NTFY_URL"], " ".join(call["args"]))
            self.assertIn(self.env["NTFY_URL"], call["config"])

    def test_failed_recovery_is_retried(self):
        self.run_watch(PROBE_FAIL="1")
        self.run_watch(expected=1, PROBE_FAIL="0", PUBLISH_FAIL="1")
        self.run_watch(PUBLISH_FAIL="0")
        self.assertIn("recovered", " ".join(self.publishes()[-1]["args"]).lower())
        count = len(self.publishes())
        self.run_watch()
        self.assertEqual(len(self.publishes()), count)

    def test_overlapping_checks_do_not_send_duplicate_alerts(self):
        import fcntl
        state = self.root / "state"
        state.mkdir()
        with (state / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_watch(PROBE_FAIL="1")
        self.assertEqual(self.publishes(), [])

    def test_notification_configuration_rejects_plaintext_and_config_injection(self):
        for url in ["http://ntfy.invalid/private-test-topic",
                    'https://ntfy.invalid/private-test-topic\noutput = "unsafe"']:
            with self.subTest(url_scheme=url.split(":")[0]):
                self.run_watch(expected=2, NTFY_URL=url)
                self.assertEqual(self.publishes(), [])

    def test_apophis_is_the_only_deployment_target_and_rebuild_includes_it(self):
        import yaml
        path = ROOT / "homelab/ansible/playbooks"
        play = yaml.safe_load((path / "provision-deadmans-switch.yml").read_text())[0]
        self.assertEqual(play["hosts"], "apophis")
        rebuild = yaml.safe_load((path / "provision-host.yml").read_text())
        self.assertIn("provision-deadmans-switch.yml", [p.get("import_playbook") for p in rebuild])


if __name__ == "__main__":
    unittest.main()
