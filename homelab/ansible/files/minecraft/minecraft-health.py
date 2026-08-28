#!/usr/bin/env python3
"""Expose Bedrock service/listener health for LAN-only monitoring."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess


def healthy() -> bool:
    process = subprocess.run(
        ["pgrep", "-u", "minecraft", "-x", "bedrock_server"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    listener = subprocess.run(
        ["ss", "-H", "-lun", "sport", "=", ":19132"],
        check=False,
        capture_output=True,
        text=True,
    )
    return process.returncode == 0 and bool(listener.stdout.strip())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        ok = healthy()
        body = b"OK\n" if ok else b"UNHEALTHY\n"
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 9098), Handler).serve_forever()
