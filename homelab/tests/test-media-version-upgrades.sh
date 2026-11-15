#!/usr/bin/env bash
# Regression contract for deliberate Radarr and Prowlarr upgrades.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
radarr="${repo_root}/homelab/ansible/playbooks/provision-radarr.yml"

grep -Fq 'radarr_version: "6.4.4.10685"' "$vars"
grep -Fq 'radarr_sha256: "a1d726129535e739d4efaf93b5fdd771bb1c78349f55ceac70e365e37b5a12a3"' "$vars"
grep -Fq 'sha256sum -c -' "$radarr"
grep -Fq 'radarr_installed_version.stdout | trim != radarr_version' "$radarr"
grep -Fq 'Prowlarr 2.7.0.5723-ls168' "$vars"
grep -Fq 'sha256:6660787a99b2e58203539583663c973b48979fc00ff2cb78dc0ea17429e1f6ef' "$vars"

printf 'PASS: Radarr and Prowlarr upgrades are pinned and reproducible\n'
