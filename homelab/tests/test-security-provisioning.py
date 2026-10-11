#!/usr/bin/env python3
"""Exercise secret-output suppression, SSH trust and VPN startup failure locally."""
import configparser
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "homelab/ansible"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("ha_metrics_hosts", ANSIBLE / "files/monitoring/ha-metrics-hosts.py")
hosts_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosts_helper)


def tasks(path):
    data = yaml.safe_load(path.read_text())
    entries = [task for play in data for task in play.get("tasks", [])] if "tasks" in data[0] else data
    def flatten(entries):
        for task in entries:
            yield task
            for key in ["block", "rescue", "always"]:
                yield from flatten(task.get(key, []))
    return list(flatten(entries))


class SecurityProvisioningTests(unittest.TestCase):
    def test_local_tls_alias_preserves_other_hosts_and_updates_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts"
            original = "127.0.0.1 localhost\n# --- BEGIN PVE ---\n127.0.1.1 fixture\n# --- END PVE ---\n"
            path.write_text(original)
            path.chmod(0o640)
            self.assertTrue(hosts_helper.update_hosts(path, "127.0.0.2", "ha-metrics.home.arpa"))
            self.assertFalse(hosts_helper.update_hosts(path, "127.0.0.2", "ha-metrics.home.arpa"))
            self.assertTrue(hosts_helper.update_hosts(path, "127.0.0.3", "ha-metrics.home.arpa"))
            self.assertTrue(path.read_text().startswith(original))
            self.assertEqual(path.read_text().count(hosts_helper.MARKER), 1)
            self.assertNotIn("127.0.0.2", path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_local_tls_alias_rejects_conflicts_without_changing_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts"
            original = "127.0.0.1 localhost\n127.0.0.2 ha-metrics.home.arpa existing\n"
            path.write_text(original)
            with self.assertRaises(ValueError):
                hosts_helper.update_hosts(path, "127.0.0.3", "ha-metrics.home.arpa")
            self.assertEqual(path.read_text(), original)

    def test_verbose_ansible_never_prints_provisioning_tokens(self):
        selected = []
        for task in tasks(ANSIBLE / "playbooks/provision-monitoring.yml"):
            if "pveum user token add" in task.get("ansible.builtin.shell", ""):
                selected.append(copy.deepcopy(task))
        for task in tasks(ANSIBLE / "playbooks/tasks/technitium-instance.yml"):
            if task.get("register") in {"tech_login", "tech_defcheck", "tech_settings", "tech_forceupdate", "tech_verify"}:
                selected.append(copy.deepcopy(task))
        self.assertEqual(len(selected), 6)
        for task in selected:
            task.pop("when", None)
            if task.get("register") == "tech_defcheck":
                task.pop("failed_when", None)  # Exercise callback redaction even if default login unexpectedly returns a token.
        fake_secret = "fixture-secret-must-never-appear-in-task-output"
        response = {"value": fake_secret, "token": fake_secret, "status": "ok",
                    "response": {"enableBlocking": True, "blockListUrls": ["https://example.invalid/list"]}}
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            for command in ["pveum", "pct"]:
                file = tmp / command
                file.write_text("#!/usr/bin/env python3\nprint(" + repr(json.dumps(response)) + ")\n")
                file.chmod(0o755)
            variables = {
                "instance": {"hostname": "fixture", "ctid": 1}, "tech_cfg_login": {"stdout": json.dumps(response)},
                "technitium_forwarders": ["https://example.invalid/dns"], "technitium_forwarder_protocol": "Https",
                "technitium_blocking_type": "NxDomain", "technitium_blocklist_urls": ["https://example.invalid/list"],
                "technitium_blocklist_update_hours": 24,
            }
            play = tmp / "test.yml"
            play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                            "vars": variables, "tasks": selected}]))
            cfg = tmp / "ansible.cfg"
            cfg.write_text("[defaults]\nstdout_callback=default\n")
            env = dict(os.environ, ANSIBLE_CONFIG=str(cfg), PATH=str(tmp) + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-vvv", str(play)],
                                    env=env, cwd=tmp, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, "fixture playbook must execute successfully")
            self.assertFalse(fake_secret in result.stdout + result.stderr, "verbose task diagnostics disclosed a token")

    def test_ansible_ssh_requires_verified_host_keys(self):
        cfg = configparser.ConfigParser()
        cfg.read(ANSIBLE / "ansible.cfg")
        self.assertTrue(cfg.getboolean("defaults", "host_key_checking"), "target identity verification must be enabled")
        self.assertIn("StrictHostKeyChecking=yes", cfg.get("ssh_connection", "ssh_common_args", fallback=""),
                      "unknown and changed host keys must fail unattended automation")

    def test_rebuilt_ha_scrape_requires_verified_tls(self):
        provisioning = tasks(ANSIBLE / "playbooks/provision-monitoring.yml")
        template = next(task["vars"]["prom_yml"] for task in provisioning if "prom_yml" in task.get("vars", {}))
        ha = template.split("- job_name: home-assistant", 1)[1].split("metric_relabel_configs:", 1)[0]
        self.assertIn("scheme: https", ha)
        self.assertIn("insecure_skip_verify: false", ha)
        self.assertIn("server_name:", ha)
        self.assertIn("ca_file:", ha)
        self.assertIn('targets: ["{{ ha_metrics_server_name }}:', ha)
        probe = template.split("- job_name: blackbox-ha-metrics-tls", 1)[1].split("- job_name: home-assistant", 1)[0]
        self.assertIn('targets: ["https://{{ ha_metrics_server_name }}:{{ ha_metrics_port | default(8443) }}/"]', probe)
        self.assertNotIn('targets: ["{{ ha_ip }}:8123"]', ha)

    def test_tls_migration_preserves_scrape_filters_and_dashboard_identity(self):
        names = {"Build the TLS job with its original dashboard identity",
                 "Build the candidate while preserving unrelated scrape jobs",
                 "Add a verified TLS probe that sends no bearer credential"}
        selected = [task for task in tasks(ANSIBLE / "playbooks/secure-ha-metrics.yml") if task["name"] in names]
        self.assertEqual(len(selected), 3)
        original = {"job_name": "home-assistant", "scheme": "http", "metrics_path": "/api/prometheus",
                    "authorization": {"credentials_file": "/protected/token"},
                    "metric_relabel_configs": [{"action": "keep", "regex": "fixture_measurement"}],
                    "static_configs": [{"targets": ["127.0.0.1:8123"], "labels": {"fixture": "retained"}}]}
        other = {"job_name": "other", "static_configs": [{"targets": ["localhost:9100"]}]}
        checks = {"name": "Verify generated security and preservation behavior", "ansible.builtin.assert": {"that": [
            "ha_metrics_tls_job.scheme == 'https'",
            "ha_metrics_tls_job.tls_config.insecure_skip_verify == false",
            "ha_metrics_tls_job.static_configs[0].targets == ['ha-metrics.home.arpa:8443']",
            "ha_metrics_tls_job.static_configs[0].labels.instance == '127.0.0.1:8123'",
            "ha_metrics_tls_job.static_configs[0].labels.fixture == 'retained'",
            "ha_metrics_tls_job.authorization == ha_metrics_job.authorization",
            "ha_metrics_tls_job.metric_relabel_configs == ha_metrics_job.metric_relabel_configs",
            "ha_metrics_candidate.scrape_configs[0] == other_job",
            "ha_metrics_probe_job.static_configs[0].targets == ['https://ha-metrics.home.arpa:8443/']",
            "ha_metrics_blackbox_candidate.modules.ha_metrics_tls.http.valid_status_codes == [200]",
            "'authorization' not in ha_metrics_blackbox_candidate.modules.ha_metrics_tls.http",
            "'basic_auth' not in ha_metrics_blackbox_candidate.modules.ha_metrics_tls.http",
        ], "quiet": True}}
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            play = tmp / "test.yml"
            play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": {"ha_ip": "127.0.0.1", "ha_metrics_port": 8443, "ha_metrics_server_name": "ha-metrics.home.arpa",
                         "ha_metrics_ct_ca": "/protected/ca.pem", "ha_metrics_job": original, "other_job": other,
                         "ha_metrics_blackbox_live": {"stdout": "modules: {}"},
                         "ha_metrics_config": {"scrape_configs": [original, other]}}, "tasks": selected + [checks]}]))
            cfg = tmp / "ansible.cfg"
            cfg.write_text("[defaults]\nstdout_callback=default\n")
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)], cwd=tmp,
                env=dict(os.environ, ANSIBLE_CONFIG=str(cfg)), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, "generated TLS config must preserve unrelated scrapes and HA semantics")

    def test_firewall_start_failure_prevents_wireguard_start(self):
        startup = next(task["ansible.builtin.shell"] for task in tasks(ANSIBLE / "playbooks/provision-qbittorrent.yml")
                       if task["name"].startswith("Enable nftables (killswitch)"))
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            pct = tmp / "pct"
            pct.write_text('#!/usr/bin/env bash\nshift 3\nexec "$@"\n')
            pct.chmod(0o755)
            systemctl = tmp / "systemctl"
            systemctl.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$FIXTURE_LOG"\n'
                                 '[[ "$*" != "restart nftables" ]]\n')
            systemctl.chmod(0o755)
            env = dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ["PATH"], FIXTURE_LOG=str(tmp / "calls"))
            result = subprocess.run(["bash", "-c", startup.replace("{{ qbittorrent_ctid }}", "1")],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, "firewall failure must fail provisioning")
            self.assertNotIn("wg-quick", (tmp / "calls").read_text(), "WireGuard must not start after firewall failure")

    def test_live_hardening_refuses_any_inactive_prerequisite(self):
        check = tasks(ANSIBLE / "playbooks/harden-qbittorrent-firewall.yml")[0]["ansible.builtin.shell"]
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            for name, body in {
                "pct": 'shift 3\nexec "$@"',
                "systemctl": '[[ "$*" != "is-active --quiet nftables" ]]',
                "nft": 'printf "policy drop;\\n"',
            }.items():
                p = tmp / name
                p.write_text("#!/usr/bin/env bash\n" + body + "\n")
                p.chmod(0o755)
            result = subprocess.run(["bash", "-c", check.replace("{{ qbittorrent_ctid }}", "1")],
                env=dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ["PATH"]),
                capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, "any inactive prerequisite must prevent applying BindsTo")

    def test_torrent_service_requires_and_follows_firewall(self):
        unit = next(task["vars"]["qb_unit"] for task in tasks(ANSIBLE / "playbooks/provision-qbittorrent.yml")
                    if "qb_unit" in task.get("vars", {}))
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read_string(unit)
        self.assertIn("nftables.service", cfg["Unit"]["Requires"].split())
        self.assertIn("nftables.service", cfg["Unit"]["After"].split())
        self.assertIn("nftables.service", cfg["Unit"].get("BindsTo", "").split(),
                      "losing the firewall must also stop the torrent service")

    def test_missing_rules_block_readiness_despite_a_healthy_tunnel(self):
        task = next(task for task in tasks(ANSIBLE / "playbooks/provision-qbittorrent.yml")
                    if task["name"] == "Install WireGuard readiness and recovery checks")
        readiness = next(item["content"] for item in task["loop"] if item["path"].endswith("vpn-ready.sh"))
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            for name, body in {
                "nft": "exit 1",
                "wg": "printf 'fixture-peer %s\\n' \"$(date +%s)\"",
                "getent": "exit 0",
                "sleep": "exit 0",
            }.items():
                p = tmp / name
                p.write_text("#!/usr/bin/env bash\n" + body + "\n")
                p.chmod(0o755)
            env = dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", "-c", readiness, "fixture", "1"], env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, "a healthy tunnel must not bypass an unloaded killswitch")


if __name__ == "__main__":
    unittest.main()
