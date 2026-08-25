#!/usr/bin/env bash
# Create one short-lived approval bound to the reviewed HA synthetic VM contract.
set -euo pipefail

usage() {
  printf 'Usage: %s <allocate|start> <test-vlan-tag> <evidence-file> <new-output.json>\n' "$0" >&2
  exit 2
}

[[ "$#" -eq 4 ]] || usage

approval_action="$1"
test_vlan_tag="$2"
evidence_file="$3"
approval_output="$4"

[[ "$approval_action" == "allocate" || "$approval_action" == "start" ]] || usage
[[ "$test_vlan_tag" =~ ^[0-9]+$ ]] || usage
(( test_vlan_tag >= 1 && test_vlan_tag <= 4094 )) || usage
[[ -f "$evidence_file" && -r "$evidence_file" && -s "$evidence_file" ]] \
  || { printf 'Evidence must be a readable, non-empty regular file.\n' >&2; exit 1; }
[[ ! -e "$approval_output" && ! -L "$approval_output" ]] \
  || { printf 'Refusing to overwrite approval artifact: %s\n' "$approval_output" >&2; exit 1; }
[[ -d "$(dirname "$approval_output")" ]] \
  || { printf 'Approval output directory does not exist.\n' >&2; exit 1; }

umask 077
python3 - "$approval_action" "$test_vlan_tag" "$evidence_file" "$approval_output" <<'PY'
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

action, vlan_text, evidence_name, output_name = sys.argv[1:]
evidence_path = Path(evidence_name)
output_path = Path(output_name)

digest = hashlib.sha256()
with evidence_path.open("rb") as evidence:
    for chunk in iter(lambda: evidence.read(1024 * 1024), b""):
        digest.update(chunk)

issued = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
expires = issued + dt.timedelta(minutes=15)
approval = {
    "schema": 1,
    "action": action,
    "node": "carter",
    "vmid": 201,
    "hostname": "ha-synthetic",
    "image_version": "18.2",
    "image_sha256": "254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e",
    "storage": "local-zfs",
    "vlan_tag": int(vlan_text),
    "contract": "carter-vm201-haos18.2-q35-2vcpu-8192mb-64gb-local-zfs-test-v1",
    "evidence_sha256": digest.hexdigest(),
    "nonce": secrets.token_hex(16),
    "issued_at_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "expires_at_utc": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
}

flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
descriptor = os.open(output_path, flags, 0o600)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(approval, output, indent=2, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
except BaseException:
    output_path.unlink(missing_ok=True)
    raise

print(f"Created {action} approval valid until {approval['expires_at_utc']}: {output_path}")
PY
