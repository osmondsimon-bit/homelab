# Phase 2 — Remote access (Tailscale) + DNS (Technitium)

**Status:** ✅ Complete — 2026-06-16
**Phase gate:** `/security-review` + `doc-auditor` + `continuity-reviewer` (full gate)

## What was delivered

- **Tailscale** subnet router — CT 110 on apophis (ADR-003), advertising the LAN. (Completed earlier in Phase 2.)
- **Technitium DNS** — CT 111, DNS-only resolver with ad/tracker/malware blocking (ADR-011):
  - Deployed on **oneill** (Intel NUC, arrived mid-phase) directly — not apophis-then-migrate.
  - DNS-only role; **UniFi keeps DHCP** and hands out the resolver. Live on the **home VLAN**; IoT/guest use the gateway for DNS (DNS-by-VLAN-role, ADR-011 — isolated VLANs can't reach a main-LAN resolver, and appliances break on blocklists; camera/management have no internet).
  - **OISD Big** blocklist (`domainswild2`) + **DoH** forwarders (Cloudflare, Quad9), `NxDomain` blocking.
  - Config is applied **declaratively via the Technitium API** by `provision-technitium.yml` from `technitium_*` group_vars, with read-back verification. Console is treated as read-only.
  - Admin password set on first install via API (`no_log`); default creds verified rejected.

## Key decisions / notes

- **oneill** built on **ZFS-on-root** (ADR-009), standalone for now — joins the cluster in Phase 4.
- Old apophis Technitium CT 111 destroyed; its address freed.
- Ansible var strategy: service identity/config in `group_vars/all.yml`; per-node hardware quirks in `host_vars/<node>.yml` (oneill = `local-zfs`). Run service playbooks with `--limit <node>`.

## Carried into Phase 3 (from the gate reviews)

- **[High] VM-level (Proxmox) backups = Phase 3 entry task** — no backup target exists; must land before any stateful service (Monitoring/Homepage) goes on oneill. (continuity-reviewer)
- **CT 111 reprovision drill** — destroy + re-provision, record RTO, to make the Ansible-rebuild path a tested fact. (continuity-reviewer)
- **DNS SPOF** — single Technitium instance; mitigations: maintenance-fallback runbook entry (added), Monitoring alert (Phase 3), 2nd instance after clustering (Phase 4).

## Verification

`dig @<technitium>` from a home-VLAN client: normal names resolve; in-list ad/tracker hostnames return NXDOMAIN; client `nslookup` confirms the Technitium IP as server.
