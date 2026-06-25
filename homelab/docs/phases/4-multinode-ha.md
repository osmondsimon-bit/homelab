# Phase 4 — Multi-node + HA ✓ CLOSED 2026-06-25

Closed via `/phase-gate` (doc-auditor + continuity-reviewer + security-review). Records what
shipped, key decisions, verification, and carry-forwards. Authoritative status: `PLAN.md`.

## What shipped

- **2-node Proxmox cluster `homelab`** = **apophis + carter** (ThinkCentre M920q, i5-8500 / 32 GB /
  256 GB SSD, matched Coffee-Lake CPU to apophis for live migration). **oneill stays standalone**
  (NOT a cluster member). No HA manager, no fencing — the single-NIC network isn't HA-grade.
- **apophis rebuilt LVM-thin → ZFS-on-root** (`rpool`, 472 GB) so storage is ZFS cluster-wide.
  All guests evacuated to carter, apophis reinstalled + rejoined, guests migrated back.
- **`pvesr` replication** of VM 200 (home-assistant) apophis→carter every 15 min (job `200-0`) +
  a written **manual-failover** runbook (start VM 200 on the survivor from the latest snapshot).
- **DNS redundancy** — 2nd Technitium resolver **CT 117 `technitium2` on carter** (`.13`),
  config-identical to CT 111 via a refactored `technitium_instances` playbook loop; independent
  node from CT 111 (oneill) so a single node loss never kills DNS.
- **Corosync ride-out** — `token: 10000` (10 s) so short blips don't drop quorum.
- **Monitoring made cluster-aware** — deduped the duplicate cluster-wide `pve_*` series in Glance
  widgets + recording rules + alerts (`max/min by(id)`); added **replication-health alerts**
  (`ReplicationStale`, `ReplicationFailing`); carter onboarded (node_exporter, pve token via
  `token_from: apophis`, Glance host pane + 2nd DNS tile).
- **Autostart codified** — every CT-create playbook now passes `--startup` matching live ordering.
- **AC power-recovery** set on all three hosts (thinklmi / BIOS) — all auto-recover from power loss.

## Key decisions / ADRs

- **ADR-009 (revised 2026-06-22):** 2-node cluster, **manual failover not auto-HA** (network not
  HA-grade); oneill standalone; replicate only the critical VM set.
- **ADR-011:** DNS redundancy delivered as a 2nd Technitium instance (keeps ad-blocking), not a
  public secondary.
- **Tailscale stays on apophis** (decided 2026-06-25) — supersedes the earlier "→ oneill" intent.
- Terraform import still deferred to cluster scale (ADR-008).
- CPU type `x86-64-v2-AES` on VM 100/200 for guaranteed live migration across the matched pair.

## Verification done

- Cluster: 2 nodes, quorate; corosync token 10000 confirmed on both nodes, no errors.
- Replication: job `200-0` first sync OK; `ReplicationStale` margin healthy; alerts evaluate clean.
- Guests: all back on apophis and running; live migration of VM 100 (mgmt-vm) survived in-session.
- DNS: CT 117 resolves + NXDOMAIN-blocks; GuestDown covers `lxc/117` (verified by a stop test —
  `min by(id)` fires exactly one alert).
- Monitoring: all node + pve targets up; one series per guest/storage (dedup verified in Prometheus).
- Security review: PASS — no findings (no new secrets/exposure; gitleaks clean on every commit).

## Gotchas recorded (full detail in runbooks.md → Phase 4b execution notes)

- apophis was reinstalled **out of order** (before `delnode`) → carter lost quorum; recovered with
  `pvecm expected 1` + `delnode` + removing stale `/etc/pve/nodes/apophis`.
- Live-migration tunnel dropped at near-line-rate on the shared 1 Gb NIC → fixed with
  `qm migrate --bwlimit 100000`.
- `pvecm add` 2FA-over-TTY kept returning 401 → removed `root@pam` TOTP over SSH to join, re-enrolled
  fresh after. **Treat 2FA as a join blocker.**

## Carried forward (continuity-reviewer — accepted at the gate, tracked in PLAN.md)

- **VM 200 manual-failover drill** — ✅ **done 2026-06-25 (early Phase 5)**: non-destructive
  clone-to-test-VM drill proved carter's replicated copy boots; procedure validated. (At Phase 4
  close this was pending, covered by the replication-health alerts; now exercised.)
- **Carter-rebuild runbook** — symmetric to the apophis 4b runbook; must include the 2FA join-blocker
  step. Not yet written.
- **Failback commands** explicit in the manual-failover runbook step 6.
- **Off-site backup** still unresolved (oneill holds the only copy) — explicitly carried.
- **CT 111 + CT 117 reprovision drills** — outstanding (now lower-risk with the 2nd resolver live).
- **DNS failover — ✅ complete 2026-06-25:** `.13` reserved in UniFi + handed out as secondary DNS on the
  home-VLAN DHCP (primary `.6`); clients fail over automatically, DNS SPOF fully removed.
- **Accepted SPOFs:** carter is the sole replication target (2-node trade); `corosync.conf` is
  live-only pmxcfs state (auto-restores from `/etc/pve` on rejoin).
