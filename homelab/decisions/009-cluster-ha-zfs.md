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
  - NUC — simple/always-on services offloaded from apophis: Tailscale, Technitium, Glance,
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

## Refinements (2026-06-22 — carter arrived; pre-cluster design review, infra-designer-reviewed)

These refine, not change, the direction above. carter = i5-8500 / 32 GB (8th-gen Coffee Lake,
same generation as apophis's i7-8700T → a migration-compatible pair). Implementation specifics
live in PLAN.md / runbooks.

- **The nodes are deliberately unequal; the NUC must never be a core-VM failover target.**
  Core/critical VMs (Home Assistant VM 200; later Vaultwarden) get HA **only on the matched
  apophis + carter pair**, enforced by a Proxmox **HA group** containing just those two. This
  lets those VMs run a high, fixed CPU type and live-migrate cleanly between the pair with **no
  penalty from the weaker node**. oneill (N150) = **quorum vote + light, reproducible services**
  (rebuilt from Ansible, never migrated) — a weak CPU is fine for a quorum vote. Storage-side HA
  = **ZFS replication apophis↔carter** for the HA-flagged set (needs apophis's LVM→ZFS migration,
  Phase 4b).

- **Single-NIC hosts → the shared network device is an ACCEPTED availability SPOF.** Each host has
  one Ethernet port, so a redundant (second) corosync ring is not available today. With all nodes
  on one shared device (gateway now, a switch later), a multi-minute outage of that device is a
  multi-minute *cluster* outage — node-HA cannot help when the network substrate itself is gone,
  and **corosync cannot distinguish "peer down" from "shared device down"** (the split-brain
  problem; quorum is the only safe response, so there is no "ignore if it's the switch" mode).
  Decision: **bound the damage rather than eliminate it** — (1) controlled, *manual* UniFi
  control-plane updates applied with the cluster in HA maintenance (auto-update disabled), since
  the observed real-world cause was a UniFi auto-update reboot (see the Zigbee outage root cause);
  (2) conservative HA scope so few nodes are fence-eligible; (3) corosync tuned to ride out short
  blips. A **second corosync ring via a USB-Gigabit NIC** is the documented future option, deferred
  (USB-NIC jitter is acceptable only on a *secondary* ring) — revisit with the new-house network.
