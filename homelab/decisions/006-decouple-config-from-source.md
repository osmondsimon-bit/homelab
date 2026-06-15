# ADR-006: Decouple configuration from published source (no real IPs in the public repo)

**Date:** 2026-06-14  
**Status:** Accepted

## Context

The repo is a **public** GitHub repository, kept that way deliberately (portfolio / shareable).
It had real internal network details committed throughout — host IPs, the LAN subnet, the
Tailscale CGNAT address, MACs. These are RFC1918 / CGNAT (not internet-routable, so the direct
risk is low), but publishing a live map of the network is unnecessary recon surface and the
author wants the repo shareable without it.

Three standard decoupling methods were considered: (1) keep config out of source via gitignored
files + committed templates; (2) replace real values with placeholders; (3) reference services by
FQDN via local DNS. We adopt **1 + 2 now**; **3 is deferred** to ride on the Phase 2 Technitium
DNS deployment (Technitium is what will resolve `service.homelab.internal` names).

## Decision

**No real network addresses appear in any committed/published file.**

- **Real values live only in gitignored local config:** `ansible/inventory/hosts.ini` and
  `ansible/inventory/group_vars/all.yml`. The repo commits `*.example` templates carrying
  `YOUR_*` placeholders; a fresh clone copies them and fills in real values.
- **All committed docs use `YOUR_*` placeholders** (`YOUR_PROXMOX_IP`, `YOUR_MGMT_VM_IP`,
  `YOUR_HA_IP`, `YOUR_TAILSCALE_LAN_IP`, `YOUR_GATEWAY_IP`, `YOUR_LAN_CIDR`,
  `YOUR_ZIGBEE_COORD_IP`, `YOUR_TAILSCALE_IP`), never real IPs/subnets/MACs.
- **Single source of truth is now two-tier:** logical facts (which hosts/VMs/LXCs exist, VMIDs,
  RAM budget, phase/service status, canonical hostnames) stay in `homelab/PLAN.md`; **real network
  addresses live only in the gitignored Ansible config**, the operator's private notes, and UniFi.
- **Git history was scrubbed** of the previously-committed real IPs (`git filter-repo
  --replace-text`) and force-pushed.
- **The `doc-auditor` agent enforces this**: any real-IP pattern in a committed file is a leak.

## Consequences

- A fresh clone is non-functional until the `*.example` files are copied and filled in — documented
  in `ansible/README.md`. Acceptable for a single-operator repo.
- PLAN.md and docs are less directly operational for the author (placeholders instead of real
  addresses); the real values are one `cat` away in the local gitignored config. Accepted as the
  cost of a public portfolio repo.
- **History scrubbing cleans the visible repo but is not a guaranteed un-publish** — values already
  pushed publicly may persist in GitHub's cached commits, forks, and search indexes. Treat the real
  addresses as "was briefly public" (low risk, RFC1918/CGNAT), not "never seen."
- The secrets policy is unchanged and still absolute (no secrets, ever); this ADR adds "no internal
  addresses either."
- **Method 3 (FQDN/local DNS)** lands with Technitium: once services resolve by name, docs and
  playbooks can reference `name.homelab.internal` instead of any address, reducing placeholder
  sprawl. Tracked in PLAN.md.
