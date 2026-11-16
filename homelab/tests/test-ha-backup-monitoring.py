#!/usr/bin/env python3
"""Verify that HA backup results survive the bounded Prometheus scrape filter."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2] / "homelab"


def keep_patterns():
    source = (ROOT / "ansible/playbooks/provision-monitoring.yml").read_text()
    provision = next(re.match(r"\s+regex: '(.+)'", line)[1]
                     for line in source.splitlines()
                     if "regex:" in line and "binary_sensor_state" in line)
    deploy = (ROOT / "ansible/playbooks/deploy-monitoring-rules.yml").read_text()
    focused = re.search(r"monitoring_ha_memory_regex: '(.+)'", deploy)[1]
    # Ansible's Jinja rendering unescapes the literal backslashes before Prometheus reads YAML.
    return [re.compile(pattern.replace("\\\\", "\\")) for pattern in [provision, focused]]


class BackupMetrics(unittest.TestCase):
    def test_both_backup_result_timestamps_are_retained(self):
        for pattern in keep_patterns():
            for prefix in ["homeassistant", "hass"]:
                for result in ["attempted", "successful"]:
                    metric = f"{prefix}_sensor_timestamp_seconds;sensor.backup_last_{result}_automatic_backup"
                    with self.subTest(metric=metric):
                        self.assertIsNotNone(pattern.fullmatch(metric))

    def test_other_backup_and_household_telemetry_stays_excluded(self):
        for pattern in keep_patterns():
            for metric in [
                "homeassistant_sensor_timestamp_seconds;sensor.backup_next_scheduled_automatic_backup",
                "homeassistant_sensor_timestamp_seconds;sensor.unrelated_timestamp",
                "homeassistant_state_change_total;sensor.backup_last_successful_automatic_backup",
                "homeassistant_sensor_data_size_mib;sensor.backup_last_successful_automatic_backup_size",
            ]:
                with self.subTest(metric=metric):
                    self.assertIsNone(pattern.fullmatch(metric))

    def test_full_and_focused_deployments_keep_the_same_metrics(self):
        self.assertEqual(keep_patterns()[0].pattern, keep_patterns()[1].pattern)


if __name__ == "__main__":
    unittest.main()
