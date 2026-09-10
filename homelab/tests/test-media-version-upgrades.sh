#!/usr/bin/env bash
# Regression contract for deliberate Radarr and Prowlarr upgrades.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
radarr="${repo_root}/homelab/ansible/playbooks/provision-radarr.yml"

grep -Fq 'radarr_version: "6.3.0.10514"' "$vars"
grep -Fq 'radarr_sha256: "41d6455c037ff267c5ad5a0f0de4502cebe8f89ec3d051da97851933d48a4047"' "$vars"
grep -Fq 'sha256sum -c -' "$radarr"
grep -Fq 'radarr_installed_version.stdout | trim != radarr_version' "$radarr"
grep -Fq 'Prowlarr 2.5.2.5491-ls159' "$vars"
grep -Fq 'sha256:c7502a75b021d964481c129c84590b9cbc40f83aadd4e553f173871bc0deaa3c' "$vars"

printf 'PASS: Radarr and Prowlarr upgrades are pinned and reproducible\n'
