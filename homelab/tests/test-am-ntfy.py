#!/usr/bin/env python3
"""Exercise real webhook requests for actionable outage and recovery notifications."""
import importlib.util
import json
from pathlib import Path
import threading
import sys
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

import yaml

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('am_ntfy', ROOT / 'homelab/ansible/files/monitoring/am-ntfy.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class Notifications(unittest.TestCase):
    def setUp(self):
        self.messages = []
        messages = self.messages

        class Sink(BaseHTTPRequestHandler):
            def do_POST(self):
                messages.append((dict(self.headers), self.rfile.read(int(self.headers['Content-Length'])).decode()))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_):
                pass

        self.sink = HTTPServer(('127.0.0.1', 0), Sink)
        bridge.NTFY_URL = f'http://127.0.0.1:{self.sink.server_port}/test-topic'
        self.webhook = HTTPServer(('127.0.0.1', 0), bridge.Handler)
        for server in [self.sink, self.webhook]:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        rules = yaml.safe_load((ROOT / 'homelab/ansible/files/monitoring/alert-rules.yml').read_text())
        self.rules = {r['alert']: r for g in rules['groups'] for r in g['rules'] if 'alert' in r}

    def tearDown(self):
        for server in [self.webhook, self.sink]:
            server.shutdown()
            server.server_close()

    def send(self, name, status):
        rule = self.rules[name]
        payload = {'alerts': [{'status': status, 'labels': {'alertname': name, **rule['labels']}, 'annotations': rule['annotations']}]}
        req = Request(f'http://127.0.0.1:{self.webhook.server_port}/alert', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urlopen(req) as response:
            self.assertEqual(response.status, 204)
        return self.messages[-1]

    def test_coordinator_outage_names_impact_and_physical_action(self):
        headers, body = self.send('ZigbeeCoordinatorUnreachable', 'firing')
        self.assertEqual(headers['Title'], 'Zigbee coordinator offline [critical]')
        self.assertEqual(headers['Priority'], 'urgent')
        self.assertIn('power', body)
        self.assertIn('Ethernet', body)
        self.assertIn('Zigbee devices', body)

    def test_recovery_does_not_repeat_the_outage_as_its_message(self):
        headers, body = self.send('ZigbeeCoordinatorUnreachable', 'resolved')
        self.assertEqual(headers['Title'], 'RESOLVED: Zigbee coordinator reachable')
        self.assertEqual(headers['Priority'], 'default')
        self.assertIn('reachable again', body)
        self.assertNotIn('unreachable (2m)', body)

    def test_bridge_message_explains_why_ha_can_look_healthy(self):
        headers, body = self.send('Zigbee2MQTTBridgeDown', 'firing')
        self.assertEqual(headers['Title'], 'Zigbee automations offline [critical]')
        self.assertIn('Home Assistant', body)
        self.assertIn('coordinator', body)

    def test_unannotated_alert_keeps_its_existing_title_and_summary(self):
        self.rules['Example'] = {'labels': {'severity': 'warning'}, 'annotations': {'summary': 'Example warning'}}
        headers, body = self.send('Example', 'firing')
        self.assertEqual(headers['Title'], 'Example [warning]')
        self.assertEqual(body, 'Example warning')


if __name__ == '__main__':
    unittest.main()
