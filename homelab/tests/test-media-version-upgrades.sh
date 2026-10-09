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
grep -Fq 'Prowlarr 2.6.5.5623-ls163' "$vars"
grep -Fq 'sha256:f9151e5bc1025c6d0a630d503210cdcb6bb55a7cc098562609d96a408d838902' "$vars"

printf 'PASS: Radarr and Prowlarr upgrades are pinned and reproducible\n'
