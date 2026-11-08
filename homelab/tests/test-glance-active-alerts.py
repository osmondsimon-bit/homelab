#!/usr/bin/env python3
"""Render the real Glance alert widget against isolated HTTP fixtures; requires GLANCE_BIN."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler

import yaml

ROOT = Path(__file__).resolve().parents[2]
BINARY = os.environ['GLANCE_BIN']
TEMPLATE = Path(os.environ.get('GLANCE_TEMPLATE', ROOT / 'homelab/ansible/templates/glance/glance.yml.j2'))


class AlertWidget(unittest.TestCase):
    def render(self, payload, code=200):
        class API(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def log_message(self, *_):
                pass

        api = HTTPServer(('127.0.0.1', 0), API)
        self.addCleanup(api.server_close)
        threading.Thread(target=api.serve_forever, daemon=True).start()
        self.addCleanup(api.shutdown)
        text = TEMPLATE.read_text()
        start = text.index('      - type: custom-api\n        title: Active Alerts')
        end = text.index('      - type: custom-api\n        title: Operational Signals', start)
        widget = yaml.safe_load(text[start:end].replace('<< glance_prometheus_url >>', f'http://127.0.0.1:{api.server_port}'))[0]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        config = {'server': {'host': '127.0.0.1', 'port': port}, 'pages': [{'name': 'Overview', 'columns': [{'size': 'full', 'widgets': [widget]}]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'glance.yml'
            path.write_text(yaml.safe_dump(config))
            check = subprocess.run([BINARY, '--config', str(path), 'config:print'], capture_output=True, text=True, timeout=10)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertNotIn('Config has errors:', check.stdout + check.stderr)
            with subprocess.Popen([BINARY, '--config', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
                try:
                    op = build_opener(ProxyHandler({}))
                    for attempt in range(50):
                        try:
                            with op.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                                page = response.read().decode()
                            # Glance loads widget content through its page endpoint.
                            with op.open(f'http://127.0.0.1:{port}/api/pages/overview/content/', timeout=2) as response:
                                page += response.read().decode()
                            return page
                        except URLError:
                            if process.poll() is not None:
                                self.fail('Glance exited before serving the widget')
                            time.sleep(0.1)
                    self.fail('Glance did not become ready')
                finally:
                    process.terminate()
                    process.wait(timeout=5)

    def test_firing_alert_shows_impact_action_and_no_private_labels(self):
        page = self.render({'status': 'success', 'data': {'alerts': [{'state': 'firing', 'labels': {'alertname': 'ZigbeeCoordinatorUnreachable', 'severity': 'critical', 'instance': 'PRIVATE_INSTANCE'}, 'annotations': {'title': 'Zigbee coordinator offline', 'summary': 'Zigbee devices may not respond', 'description': 'Check power and Ethernet'}}]}})
        for value in ['Zigbee coordinator offline', 'Zigbee devices may not respond', 'Check power and Ethernet', 'role="alert"']:
            self.assertIn(value, page)
        self.assertNotIn('No firing alerts', page)
        self.assertNotIn('PRIVATE_INSTANCE', page)

    def test_pending_alert_is_not_shown_as_firing(self):
        page = self.render({'status': 'success', 'data': {'alerts': [{'state': 'pending', 'labels': {'alertname': 'PendingExample'}}]}})
        self.assertIn('No firing alerts', page)
        self.assertNotIn('PendingExample', page)

    def test_empty_alerts_show_clear_state(self):
        self.assertIn('No firing alerts', self.render({'status': 'success', 'data': {'alerts': []}}))

    def test_failed_api_never_shows_clear_state(self):
        page = self.render({'status': 'error'}, code=503)
        self.assertIn('Alert status unavailable', page)
        self.assertNotIn('No firing alerts', page)


if __name__ == '__main__':
    unittest.main()
