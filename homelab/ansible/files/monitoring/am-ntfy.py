#!/usr/bin/env python3
"""Minimal Alertmanager -> ntfy webhook bridge (ADR-013).

Alertmanager has no native ntfy receiver, so it POSTs its webhook JSON here and we
translate each alert into an ntfy push (title/priority/tags by status + severity).
Stdlib only — no pip deps, runs as a hardened systemd unit (DynamicUser) on the
monitoring CT. The ntfy URL (base + private topic) comes from $NTFY_URL via an
EnvironmentFile so the topic never lands in the unit file or logs.

This file is copied into the CT verbatim and is NOT Ansible-templated.
"""
import json
import os
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

NTFY_URL = os.environ.get("NTFY_URL")
PORT = int(os.environ.get("PORT", "9094"))


def push(title, priority, tags, body):
    req = urllib.request.Request(
        NTFY_URL,
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": tags},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as exc:  # never crash the bridge on a delivery hiccup
        print(f"am-ntfy: ntfy push failed: {exc}", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        for alert in payload.get("alerts", []):
            labels = alert.get("labels", {})
            ann = alert.get("annotations", {})
            name = labels.get("alertname", "alert")
            sev = labels.get("severity", "")
            inst = labels.get("instance", "")
            summary = ann.get("summary") or ann.get("description") or name
            if alert.get("status") == "resolved":
                title = f"RESOLVED: {name}"
                priority, tags = "default", "white_check_mark"
            else:
                title = f"{name} [{sev}]" if sev else name
                priority = "urgent" if sev == "critical" else "high"
                tags = "rotating_light"
            body = summary if not inst else f"{summary}\n{inst}"
            push(title, priority, tags, body)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):  # cheap health endpoint
        self.send_response(200 if NTFY_URL else 503)
        self.end_headers()

    def log_message(self, *_):  # silence default request logging
        pass


if __name__ == "__main__":
    if not NTFY_URL:
        sys.exit("am-ntfy: NTFY_URL not set (EnvironmentFile missing?)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
