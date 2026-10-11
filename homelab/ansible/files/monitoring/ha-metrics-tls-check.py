#!/usr/bin/env python3
"""Verify local HA TLS identity before sending its protected metrics credential."""
import argparse
import http.client
import json
import socket
import ssl
from pathlib import Path


def check_metrics(address, port, server_name, ca_file, token_file):
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # The SAN identity is independent of the LAN routing address; DNS is not required.
    with socket.create_connection((address, port), timeout=10) as tcp:
        with context.wrap_socket(tcp, server_hostname=server_name) as secure:
            token_path = Path(token_file)
            if token_path.stat().st_mode & 0o077:
                raise ValueError("metrics token file must be private")
            token = token_path.read_text().strip()
            if not token or any(char in token for char in "\r\n"):
                raise ValueError("invalid metrics token file")
            client = http.client.HTTPConnection(server_name, port, timeout=10)
            client.sock = secure
            try:
                client.request("GET", "/api/prometheus", headers={"Authorization": "Bearer " + token})
                response = client.getresponse()
                body = response.read(8 * 1024 * 1024 + 1)
                if response.status != 200 or len(body) > 8 * 1024 * 1024:
                    raise ValueError("metrics endpoint did not return a bounded successful response")
                if not any(line.startswith((b"# HELP ", b"# TYPE ")) for line in body.splitlines()):
                    raise ValueError("endpoint did not return Prometheus metrics")
            finally:
                client.close()
    return {"tls_verified": True, "authenticated_metrics": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", required=True)
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--token-file", default="/etc/prometheus/ha_token")
    args = parser.parse_args()
    try:
        result = check_metrics(args.address, args.port, args.server_name, args.ca_file, args.token_file)
    except (OSError, ValueError, http.client.HTTPException):
        # Errors can contain private hostnames. Never print credentials, endpoints or bodies.
        print("HA metrics preflight failed: check TLS trust, identity, expiry and endpoint access")
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
