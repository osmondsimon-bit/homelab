#!/usr/bin/env python3
"""Manage only the monitoring guest's LAN alias for the HA TLS identity."""
import ipaddress
from pathlib import Path
import re
import sys

MARKER = "# homelab HA metrics TLS identity"


def update_hosts(path, address, name):
    address = str(ipaddress.ip_address(address))
    if not re.fullmatch(r"[A-Za-z0-9.-]+", name) or not any(c.isalpha() for c in name):
        raise ValueError("Invalid TLS DNS identity")
    original = path.read_text()
    retained = []
    for line in original.splitlines(keepends=True):
        if line.rstrip().endswith(MARKER):
            continue
        fields = line.split("#", 1)[0].split()
        if name.lower() in [alias.lower() for alias in fields[1:]] and fields[0] != address:
            raise ValueError("Conflicting unmanaged HA TLS alias")
        retained.append(line)
    content = "".join(retained)
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"{address} {name} {MARKER}\n"
    if content == original:
        return False
    # Preserve the existing inode/permissions, including on container bind mounts.
    path.write_text(content)
    return True


if __name__ == "__main__":
    try:
        changed = update_hosts(Path("/etc/hosts"), sys.argv[1], sys.argv[2])
        print("changed" if changed else "unchanged")
    except (OSError, ValueError, IndexError):
        sys.exit("HA TLS alias setup failed; inspect inputs and existing aliases privately.")
