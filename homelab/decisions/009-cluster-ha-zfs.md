# ADR-009: 3-node Proxmox cluster + ZFS replication for resilience (manual failover, local storage)

**Date:** 2026-06-14 (HA approach revised 2026-06-22 — automatic HA manager rejected; see Refinements)  
**Status:** Accepted — **Phase 4 complete (2026-06-25)**; capacity model refined
2026-07-22. The 2-node cluster `homelab` (apophis + carter) is live; oneill stays
standalone; `pvesr` replication + manual failover for VMs 118/200 is in production. The
"3-node" framing in the title/Context below is the original direction — see **Refinements**
for the as-built 2-node and asymmetric-capacity decisions.

## Context

Today everything runs on a single host (apophis). Two more nodes are coming: a low-power **KAMRUI
Essenx E2 N150 mini-PC** (decent RAM) soon, and a **2nd ThinkCentre M920Q** in ~a month. The goal is
high availability for critical VMs (the Home Assistant VM especially) so a node failure doesn't
take them down, and to offload simple services onto the E2 so apophis keeps its CPU headroom for
Plex transcoding.

The constraint: **all local storage, no NAS/shared storage** (and none until the new house).
Proxmox HA normally wants shared storage so a VM can restart elsewhere — but **ZFS replication**
provides the same failover on purely local disks, at the cost of a small data-loss window (async
replication interval).

## Decision

Build a **3-node Proxmox cluster**: apophis + KAMRUI Essenx E2 + 2nd ThinkCentre M920Q.

- **Storage:** standardise each node's local storage on **ZFS**. New nodes (Essenx E2, ThinkCentre) are
  built on ZFS from the start; apophis migrates from LVM-thin to ZFS (rebuild/restore — planned).
- **Resilience via replication (HA-manager part revised 2026-06-22):** use Proxmox **ZFS
  replication** (per-VM, e.g. every 1–15 min) so a recent copy of each critical VM lives on a
  second node. *The original plan added the automatic HA manager for auto-restart; that was
  **rejected 2026-06-22** (see Refinements) in favour of **manual failover** — the automatic HA
  manager is unsafe on a single-network-path lab.* Accept the small data-loss window inherent to
  async replication.
- **Quorum:** three nodes give clean quorum (tolerates one node down). No QDevice needed.
- **Service placement:**
  - apophis — compute-heavy: Plex (QuickSync iGPU), media stack.
  - Essenx E2 — simple/always-on services offloaded from apophis: Tailscale, Technitium, Glance,
    Monitoring.
  - ThinkCentre — failover target + spare capacity.
- **HA-flagged VMs:** Home Assistant VM first; others as warranted.

## Consequences

- Real failover for critical VMs on local disks — no NAS required. The trade is a small RPO
  (data-loss window) equal to the replication interval; acceptable for HA/home services.
- **apophis must move to ZFS** (it's LVM-thin today) — a deliberate migration (backup/rebuild), best
  done once VM-level backups exist so it's low-risk. Sequenced in Phase 4.
- Mixed CPUs (i7-8700T vs N150 vs M920Q) are fine for HA *failover* (cold restart on another node);
  **live migration** between different CPU generations needs a compatible/lowest-common CPU type
  (e.g. set VM CPU type accordingly) or it may fail.
- ZFS wants RAM (ARC) — size node RAM with that in mind; the E2's "decent RAM" helps.
- Offloading simple services to the E2 frees apophis CPU for Plex (the original driver).
- Networking: all nodes on the management/Home VLAN with cluster traffic; revisit a dedicated
  cluster/replication link if bandwidth becomes a factor.
- Backups (ADR-pending / PLAN) are a prerequisite for the apophis ZFS migration and for treating HA
  as truly safe — sequenced alongside the cluster, not after.

## Refinements (2026-06-22 — carter arrived; pre-cluster design review, infra-designer-reviewed)

carter = i5-8500 / 32 GB (8th-gen Coffee Lake, same generation as apophis's i7-8700T → a
migration-compatible pair). The first refinement **materially changes** the HA approach above.
Implementation specifics live in PLAN.md / runbooks.

- **Automatic HA manager REJECTED — use MANUAL failover.** The original decision assumed the
  Proxmox HA manager would auto-restart a flagged VM on a surviving node. That is the wrong fit
  for this lab: every host has a **single NIC**, all nodes share **one network device** (gateway
  now, a switch later), **no second corosync ring is possible**, and redundant switching is never
  planned (pre-new-house). The dominant failure is therefore a **common-mode network outage** that
  hits all nodes at once — and the HA manager's watchdog reacts to the resulting quorum loss by
  **fencing (hard-rebooting) healthy nodes**: harm with no benefit, since there is nowhere to fail
  over to when the network itself is gone. corosync also **cannot distinguish "peer down" from
  "shared device down"** (split-brain; quorum is the only safe response), so there is no "ignore
  if it's the switch" mode to build. Decision:
  - **Run the cluster with NO HA-flagged resources** → the watchdog is never armed → a network
    blip is **benign**: running VMs keep running; `/etc/pve` just goes read-only on the minority
    side until quorum returns. This also makes corosync jitter on the shared NIC non-dangerous.
  - **Critical-VM resilience = scheduled ZFS replication + MANUAL failover.** Replicate the HA VM
    (and later Vaultwarden) **apophis↔carter** (matched pair; oneill is not a target) every few
    minutes; if a node truly dies, start the VM on the survivor from the latest snapshot via a
    documented runbook. A few minutes of attention for a rare event.
  - Right trade here: a single *node* hardware death (where auto-HA helps) is rare; *network* blips
    (where auto-HA harms) are common. Manual failover keeps the upside and drops the downside.

- **Cluster scope: apophis + carter ONLY (2 nodes); oneill stays STANDALONE** (revised 2026-06-22 —
  supersedes the original "3-node" framing). The cluster exists purely for **live-migration +
  `pvesr` replication** of the critical VMs across the matched Coffee-Lake pair. **oneill is NOT a
  cluster member** (nor a QDevice): its guests (Technitium, Monitoring, Glance, PBS) are
  reproducible from Ansible — or, for PBS datastore *state*, a separate off-site-backup concern —
  and since we run **no auto-HA**, the only thing 3-node membership would add is *seamless quorum*,
  which isn't worth evacuating oneill (that would drop home-VLAN DNS). **2-node quorum:** a node-down
  makes `/etc/pve` read-only (running VMs keep running); **manual failover runs `pvecm expected 1`**
  first (runbook). Live-migration across apophis↔carter uses a fixed CPU type (not `host`). DNS
  redundancy is a *service-layer* concern (gateway as secondary DNS, and/or a 2nd Technitium), not a
  reason to cluster oneill.

- **Resilience leans on independent, non-cluster mechanisms** (higher ROI here than node-HA):
  per-guest **`onboot=1` + startup order/delay** so VMs auto-recover after any reboot; **host BIOS
  set to power on after AC loss**; a **UPS that also covers the network device** so a power blip
  doesn't cause the common-mode outage at all; **service-level redundancy** (2nd Technitium for
  DNS); PBS backups as the ultimate fallback. See the power-loss/autostart runbook. A second
  corosync ring or QDevice is not planned. The operator accepts the documented `pvecm expected 1`
  recovery step when one clustered node is truly down. Revisit quorum design only if the rejected
  automatic-HA decision changes.

- **Controlled control-plane updates** regardless of the above: disable UniFi auto-update (gateway
  + switch), apply firmware manually in a window, and alert on pending updates via existing
  unpoller metrics → ntfy. (A UniFi auto-update reboot was the root cause of the 2026-06-21 Zigbee
  outage.)

## Refinement (2026-07-22 — Apophis reduced to 16 GB)

Apophis's original Lenovo 16 GB SO-DIMM failed, leaving the later aftermarket 16 GB module as its
only working RAM. A live three-node capacity review is recorded in
`docs/apophis-16gb-capacity-review-2026-07-22.md`. The operator accepted a no-purchase 16 GB
operating model with explicit service tiers.

- **Normal placement is asymmetric.** Carter runs VM 200 (Home Assistant, 8 GB) and VM 118
  (Vaultwarden, 2 GB), plus VM 127 and CT 117. Their `pvesr` jobs target Apophis. Apophis runs VM
  100 (management, 10 GB) and CT 110 by default. oneill's placement is unchanged.
- **Media is a capacity tier, not an autostart promise.** VM 125 and CTs 120/121/123/124 remain
  `onboot=0`. Jellyfin may be trialled first. Restoring the complete media workflow requires a
  separate measured change: validate VM 100 at 6 GB, move VM 125 to Carter, then start the
  storage-bound media LXCs incrementally while Apophis retains at least 3 GiB `MemAvailable`.
- **Replication is preserved; simultaneous compute failover is reduced.** An Apophis loss is still
  well covered: HA/Vaultwarden remain on Carter and cold VM 128 can start there. A Carter loss is
  capacity-constrained: stop media, use VM 100 to perform the recovery, prove an independent
  operator path to Apophis, then stop VM 100 before starting both VM 200 and VM 118 on Apophis.
  Their combined ceiling with CT 110 is 10.25 GiB. The primary management VM is unavailable until
  Carter returns or one of the critical VMs stops.
- **Describe this honestly as replicated recovery with asymmetric capacity.** Data/recovery
  redundancy remains. Symmetric runtime capacity does not. Full media autostart and a promise that
  management + HA + Vaultwarden survive either cluster-node failure simultaneously are no longer
  part of the accepted design.
- **Purchase triggers are requirements, not nostalgia for the old diagram.** Restore Apophis to
  32 GB if continuous management plus both critical replicas during Carter failure is required,
  full-time media must coexist with an 8–10 GB VM 100, the 3 GiB host guardrail fails, or managing
  service tiers becomes less acceptable than the RAM cost.

This refinement does not resize guests, move VM 125, or re-enable media. Those remain deliberate,
separately validated operations.
