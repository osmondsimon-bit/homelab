#!/usr/bin/env python3
"""Verify HA metrics credentials only cross an authenticated TLS connection."""
import http.server
import importlib.util
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("tls_check", ROOT / "homelab/ansible/files/monitoring/ha-metrics-tls-check.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class MetricsTLS(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.tmp = Path(self.directory.name)
        self.cert = self.tmp / "server.crt"
        self.key = self.tmp / "server.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
                        "-nodes", "-days", "1", "-subj", "/CN=ha-metrics.home.arpa",
                        "-addext", "subjectAltName=DNS:ha-metrics.home.arpa", "-keyout", str(self.key),
                        "-out", str(self.cert)], capture_output=True, check=True)
        self.token = self.tmp / "token"
        self.token.write_text("fixture-metrics-credential")
        self.token.chmod(0o600)
        self.requests = []
        requests = self.requests

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization")))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"# HELP fixture Fixture metric\nfixture 1\n")

            def log_message(self, *_):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def check(self, identity="ha-metrics.home.arpa", ca=None):
        return checker.check_metrics("127.0.0.1", self.server.server_port, identity,
                                     str(ca or self.cert), str(self.token))

    def test_trusted_identity_receives_the_credential(self):
        self.assertTrue(self.check()["authenticated_metrics"])
        self.assertEqual(self.requests, [("/api/prometheus", "Bearer fixture-metrics-credential")])

    def test_wrong_identity_receives_no_credential(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.check(identity="wrong.home.arpa")
        self.assertEqual(self.requests, [])

    def test_untrusted_certificate_receives_no_credential(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            checker.check_metrics("127.0.0.1", self.server.server_port, "ha-metrics.home.arpa",
                                  ssl.get_default_verify_paths().cafile, str(self.token))
        self.assertEqual(self.requests, [])

    def test_nonprivate_token_file_is_rejected(self):
        self.token.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            self.check()
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
