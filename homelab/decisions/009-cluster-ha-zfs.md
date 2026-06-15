# ADR-009: 3-node Proxmox cluster with HA via ZFS replication (local storage)

**Date:** 2026-06-14  
**Status:** Accepted (direction; executed as hardware arrives)

## Context

Today everything runs on a single host (apophis). Two more nodes are coming: a low-power **Intel
NUC** (decent RAM) soon, and a **2nd ThinkCentre M920Q** in ~a month. The goal is high availability
for critical VMs (the Home Assistant VM especially) so a node failure doesn't take them down, and
to offload simple services onto the NUC so apophis keeps its CPU headroom for Plex transcoding.

The constraint: **all local storage, no NAS/shared storage** (and none until the new house).
Proxmox HA normally wants shared storage so a VM can restart elsewhere — but **ZFS replication**
provides the same failover on purely local disks, at the cost of a small data-loss window (async
replication interval).

## Decision

Build a **3-node Proxmox cluster**: apophis + Intel NUC + 2nd ThinkCentre M920Q.

- **Storage:** standardise each node's local storage on **ZFS**. New nodes (NUC, ThinkCentre) are
  built on ZFS from the start; apophis migrates from LVM-thin to ZFS (rebuild/restore — planned).
- **HA via replication:** use Proxmox **ZFS replication** (per-VM, e.g. every 1–15 min) + the HA
  manager so a flagged VM restarts on a surviving node from the latest replicated snapshot.
  Accept the small data-loss window inherent to async replication.
- **Quorum:** three nodes give clean quorum (tolerates one node down). No QDevice needed.
- **Service placement:**
  - apophis — compute-heavy: Plex (QuickSync iGPU), media stack.
  - NUC — simple/always-on services offloaded from apophis: Tailscale, Technitium, Homepage,
    Monitoring.
  - ThinkCentre — failover target + spare capacity.
- **HA-flagged VMs:** Home Assistant VM first; others as warranted.

## Consequences

- Real failover for critical VMs on local disks — no NAS required. The trade is a small RPO
  (data-loss window) equal to the replication interval; acceptable for HA/home services.
- **apophis must move to ZFS** (it's LVM-thin today) — a deliberate migration (backup/rebuild), best
  done once VM-level backups exist so it's low-risk. Sequenced in Phase 4.
- Mixed CPUs (i7-8700T vs NUC vs M920Q) are fine for HA *failover* (cold restart on another node);
  **live migration** between different CPU generations needs a compatible/lowest-common CPU type
  (e.g. set VM CPU type accordingly) or it may fail.
- ZFS wants RAM (ARC) — size node RAM with that in mind; the NUC's "decent RAM" helps.
- Offloading simple services to the NUC frees apophis CPU for Plex (the original driver).
- Networking: all nodes on the management/Home VLAN with cluster traffic; revisit a dedicated
  cluster/replication link if bandwidth becomes a factor.
- Backups (ADR-pending / PLAN) are a prerequisite for the apophis ZFS migration and for treating HA
  as truly safe — sequenced alongside the cluster, not after.
