#!/usr/bin/env python3
"""Per-router health endpoint for Glance (:9099). Returns 200 iff tailscaled is active AND this node
is advertising the configured subnet route, else 503 — real per-router status so a broken router
shows RED even when Tailscale's control plane is fine. The route is read from
/etc/tailscale-health.route (written at deploy time from gitignored config, per ADR-006 — never
hardcoded/committed)."""
import http.server, subprocess, json
def healthy():
    try:
        route = open("/etc/tailscale-health.route").read().strip()
        if not route:
            return False
        if subprocess.run(["systemctl", "is-active", "--quiet", "tailscaled"]).returncode != 0:
            return False
        d = json.loads(subprocess.check_output(["tailscale", "status", "--json"], timeout=5))
        return route in (d.get("Self", {}).get("AllowedIPs") or [])
    except Exception:
        return False
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ok = healthy()
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "text/plain"); self.end_headers()
        self.wfile.write(b"OK\n" if ok else b"UNHEALTHY\n")
    def log_message(self, *a): pass
http.server.HTTPServer(("0.0.0.0", 9099), H).serve_forever()
