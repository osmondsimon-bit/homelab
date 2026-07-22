# Apophis 16 GB Capacity and Resilience Review — 2026-07-22

## Overview

This review determines whether Apophis can remain a 16 GB Proxmox node after its original Lenovo
16 GB SO-DIMM failed, leaving the later aftermarket 16 GB SO-DIMM as the only working module. It
uses live node and guest configuration captured during the incident, not the previous 32 GB design
assumption in `PLAN.md`.

**Review status:** Recommendation issued; implementation decision pending operator acceptance.
No runtime sizing or placement changes are authorized by this review alone.

## Executive conclusion

**Apophis can remain at 16 GB without an immediate RAM purchase, but only under a tiered service
model.** It cannot safely resume the former 32 GB placement, and it cannot provide simultaneous
capacity for the management VM, Home Assistant, Vaultwarden, and the media stack during a Carter
failure.

The recommended no-purchase trial is:

- keep Home Assistant (VM 200) and Vaultwarden (VM 118) running on Carter
- keep the primary management VM (VM 100) and Tailscale (CT 110) running on Apophis
- keep all media guests at `onboot=0` initially; start only the media services currently needed
- preserve ZFS replication for VMs 118 and 200 back to Apophis
- explicitly accept that a Carter failure requires stopping VM 100 before both replicated critical
  VMs can run on 16 GB Apophis

This retains **data/recovery redundancy** but reduces **simultaneous compute-capacity redundancy**.
That is a real architectural downgrade, not merely a placement change.

## Trigger and priorities

On 2026-07-22, one of Apophis's two 16 GB SO-DIMMs was identified as faulty. The failed module was
the machine's original Lenovo RAM, not the recently purchased expansion module. Apophis returned
with approximately 16 GB physical RAM while its guests were autostarting under the old 32 GB-era
configuration.

The operator's stated priority is:

1. primary management VM
2. Home Assistant
3. critical supporting services such as Vaultwarden and remote access
4. media serving and acquisition when capacity permits
5. media automation is expendable during degraded operation or host failure

During containment, the media guests were stopped and their autostart disabled. Home Assistant was
live-migrated to Carter and verified operational. Vaultwarden was already on Carter.

## Live evidence

The following snapshot was supplied directly from each Proxmox node on 2026-07-22. `Available` is
the Linux `MemAvailable` value. Guest values below are configured ceilings, not measured working
sets; they provide the conservative boundary needed for failover planning.

| Node | Physical RAM shown | Used | Available | Host swap | Running guest ceiling |
|---|---:|---:|---:|---:|---:|
| Apophis | 15 GiB | 7.4 GiB | 8.1 GiB | 0 | 10.25 GiB |
| Carter | 31 GiB | 10 GiB | 20 GiB | 0 | 13 GiB |
| oneill | 15 GiB | 4.1 GiB | 11 GiB | 0 | 7.5 GiB |

All three hosts have no swap. Normal operation must therefore retain real memory headroom rather
than treating disk-backed swap as an emergency buffer.

### Apophis

| Guest | Role | State | Memory ceiling | Autostart |
|---|---|---|---:|---|
| VM 100 | Primary management | Running | 10 GiB | Yes |
| CT 110 | Tailscale subnet router | Running | 0.25 GiB | Yes |
| VM 125 | Seerr/Prowlarr/ByParr/Gluetun | Stopped | 3 GiB | No |
| CT 120 | Jellyfin | Stopped | 2 GiB | No |
| CT 121 | qBittorrent | Stopped | 2 GiB | No |
| CT 123 | Sonarr | Stopped | 1 GiB | No |
| CT 124 | Radarr | Stopped | 1 GiB | No |

The complete Apophis guest ceiling is **19.25 GiB**, before Proxmox and ZFS. The old full-placement
configuration is therefore impossible on a 16 GB host even if normal working sets are lower than
their configured ceilings.

The contained state is healthy: VM 100 plus CT 110 have a 10.25 GiB ceiling, while the host reports
8.1 GiB available. A simultaneous observation inside VM 100 reported only about 1 GiB used, 8.6
GiB available, and no use of its 3.8 GiB guest swap. This demonstrates current headroom but does
not prove that VM 100's prior peak workloads fit a smaller ceiling.

### Carter

| Guest | Role | State | Memory ceiling | Autostart |
|---|---|---|---:|---|
| VM 118 | Vaultwarden | Running | 2 GiB | Yes |
| VM 127 | Actual Budget | Running | 2 GiB | Yes |
| VM 200 | Home Assistant | Running | 8 GiB | Yes |
| CT 117 | Secondary Technitium | Running | 1 GiB | Yes |
| VM 128 | Independent cold management VM | Stopped | 8 GiB | No |
| VM 199 | Unexplained `mgmt-vm` instance | Stopped | 10 GiB | No |

Carter's running guest ceiling is 13 GiB with 20 GiB host memory available. Starting intentional
cold VM 128 after an Apophis failure raises the ceiling to 21 GiB, which still leaves substantial
host headroom.

VM 199 is excluded from every recovery budget. `PLAN.md` records the 2026-06-17 VM 199 restore-test
guest as destroyed with `--purge`, but a stopped VM 199 now exists on Carter. Its origin, NIC state,
storage use, and protection status must be established before a separate cleanup decision. It must
not be started merely because it resembles VM 100.

### oneill

| Guest | Role | State | Memory ceiling | Autostart |
|---|---|---|---:|---|
| CT 111 | Primary Technitium | Running | 1 GiB | Yes |
| CT 112 | PBS | Running | 2 GiB | Yes |
| CT 113 | HA backup share | Running | 0.5 GiB | Yes |
| CT 114 | Monitoring | Running | 3 GiB | Yes |
| CT 115 | Glance | Running | 0.5 GiB | Yes |
| CT 116 | Infrastructure portal | Running | 0.25 GiB | Yes |
| CT 126 | Independent Tailscale router | Running | 0.25 GiB | Yes |

oneill has substantial current memory headroom. That spare capacity should not be treated as free
general compute by default: oneill deliberately preserves a separate failure domain for DNS,
backups, monitoring, HA backups, and remote routing, and it is not a member of the Proxmox cluster.

## Design constraints

1. Reserve at least **3 GiB `MemAvailable`** on 16 GB Apophis during sustained operation. This is a
   conservative local operating guardrail for Proxmox, ZFS ARC, kernel memory, and workload bursts;
   it is not a vendor sizing formula.
2. Do not rely on memory overcommit, ballooning, or host swap to make a failure budget pass.
3. Jellyfin stays on Apophis because its QuickSync path uses Apophis's iGPU.
4. Jellyfin, qBittorrent, Sonarr, and Radarr currently use bind mounts from Apophis's USB media
   filesystem. Moving them would require a new shared-storage design and would weaken the existing
   single-filesystem hardlink model.
5. VM 125 has no media bind mount and is the easiest media component to relocate to Carter if the
   full media workflow is restored.
6. oneill remains standalone. Moving a cluster VM there is not a routine cluster migration and is
   not justified solely to consume spare RAM.

## Options considered

| Option | Normal service availability | Failure capacity | Cost/complexity | Assessment |
|---|---|---|---|---|
| Restore Apophis to 32 GB | Full existing stack | Best match to current runbooks | RAM purchase; reinvestment in an old host | Safest, but not required immediately |
| Keep 16 GB with tiered services | Management and core services; selective media | Carter loss requires stopping management before both critical replicas start | No purchase; operational discipline | **Recommended trial** |
| Resize VM 100 and relocate VM 125 | Can return most/all media in normal operation | Carter-loss constraint remains | Sizing validation plus migration | Optional second stage |
| Move workloads to oneill | Uses visible spare RAM | Couples recovery services to extra workload; standalone migration/rebuild complexity | Architectural sprawl | Rejected as the default |

## Recommended architecture

### Stage 1 — no-purchase, no-resize trial

Use the current contained placement as the temporary steady state:

- **Apophis:** VM 100 and CT 110 only by default
- **Carter:** VM 118, VM 127, VM 200, and CT 117
- **oneill:** unchanged
- **Media guests:** remain `onboot=0`

Jellyfin may be the first media guest trialled because serving existing media matches the stated
priority better than acquisition or automation. Start media guests one at a time and observe both
the immediate working set and a representative workload before adding the next service.

Do not start VM 125 on Apophis while VM 100 retains a 10 GiB ceiling as part of an automatic boot
path. Its 3 GiB ceiling consumes most of the conservative host reserve before the storage-bound
media LXCs start.

### Stage 2 — optional fuller media profile

If full-time media becomes desirable, test this proposed profile separately:

- validate VM 100 at **6 GiB** through a controlled restart and representative Codex/Claude/Ansible
  workload
- migrate stopped VM 125 to Carter, where its 3 GiB ceiling is affordable
- retain CTs 120, 121, 123, and 124 on Apophis because of the iGPU and USB bind mounts

That produces an Apophis guest ceiling of approximately **12.25 GiB**:

| Apophis guest | Proposed ceiling |
|---|---:|
| VM 100 | 6 GiB |
| CT 110 | 0.25 GiB |
| CT 120 | 2 GiB |
| CT 121 | 2 GiB |
| CT 123 | 1 GiB |
| CT 124 | 1 GiB |

This leaves roughly 3–4 GiB nominal host space, but it is not accepted until peak measurements and
a staged workload test demonstrate the 3 GiB `MemAvailable` guardrail. The fact that VM 100 is
lightly used at one instant is insufficient evidence to permanently cut its allocation.

## Failure-state analysis

### Apophis fails

This remains the strong direction of the design:

1. HA and Vaultwarden continue on Carter.
2. CT 126 on oneill preserves the independent Tailscale route.
3. Start cold VM 128 on Carter if the primary management VM is unavailable.

Carter then has a 21 GiB configured running ceiling, leaving about 10 GiB nominal host capacity.
If VM 125 is later moved to Carter, the ceiling becomes 24 GiB and still fits with useful headroom.
Apophis failure therefore remains operationally supportable without buying RAM.

### Carter fails

This is the capacity-limited direction. With current guest sizes, 16 GB Apophis cannot run:

- VM 100 at 10 GiB
- VM 200 at 8 GiB
- VM 118 at 2 GiB
- CT 110 at 0.25 GiB
- the Proxmox/ZFS host

The guest ceiling alone would be 20.25 GiB. The accepted emergency sequence for a 16 GB design
must therefore be capacity-aware:

1. Stop all media guests.
2. Use VM 100 to confirm Carter is truly down, restore quorum deliberately, inspect replication,
   and prepare the critical-VM recovery.
3. Ensure an operator desktop has direct administrative access to Apophis.
4. Shut down VM 100 before starting both VM 200 and VM 118 from their Apophis replicas.
5. Run HA, Vaultwarden, and CT 110 at a combined 10.25 GiB ceiling until Carter returns.

This keeps home automation and the secrets service available, but the primary management VM is not
simultaneously available. If continuous management plus HA plus Vaultwarden during Carter failure
is a firm requirement, Apophis must regain more physical RAM or the critical guests must be resized
after evidence-based testing.

The manual-failover runbook was written for 32 GB Apophis and did not state this shutdown
requirement when the review began. It was revised when the 16 GB design was accepted.

### oneill fails

The clustered compute budget is unchanged. Secondary Technitium on Carter preserves DNS redundancy,
but PBS, HA backup landing, monitoring, Glance, and the independent Tailscale route are unavailable
until oneill returns. This is the existing ADR-009/ADR-012 risk and is not worsened by leaving
Apophis at 16 GB.

## Redundancy impact

| Capability | 32 GB Apophis assumption | Proposed 16 GB model |
|---|---|---|
| VM 118/200 replica data | Present | Preserved if jobs remain enabled and healthy |
| Apophis-loss recovery | Carter runs critical VMs and management recovery | Preserved |
| Carter-loss recovery | Apophis can host management plus critical replicas | Selective; VM 100 must stop for both replicas |
| Media during a node failure | Could remain available depending on failure | First service tier sacrificed |
| Full-stack autostart on Apophis | Previously intended | Unsafe and prohibited |

The correct description is **replicated recovery with asymmetric capacity**, not symmetric failover.

## Operational guardrails

- Keep media guests `onboot=0` until a reviewed profile proves they fit.
- Treat sustained Apophis `MemAvailable < 3 GiB`, guest swapping under representative load, any OOM
  event, or material memory PSI as a failed 16 GB validation.
- Do not start multiple media guests together merely because the current idle snapshot has 8.1 GiB
  available.
- Retain the 100000 KiB/s cross-node migration cap from the existing single-NIC runbook.
- Verify both replication jobs after every migration. During this incident, VM 200 job `200-0` was
  enabled and healthy on Carter; VM 118 job `118-0` was observed disabled and was instructed to be
  re-enabled and synchronized. Its final enabled state remains a verification item.
- Prove direct operator access to Apophis before accepting the Carter-failure sequence that shuts
  down VM 100.
- VM 199 was not counted as a recovery control node. It was subsequently identified as a stale,
  stopped recovery clone and purged; see the implementation state below.

## Purchase triggers

Do not buy RAM merely to restore the old diagram. Reconsider restoring Apophis to 32 GB when any of
these becomes a real requirement or measured condition:

1. VM 100, HA, and Vaultwarden must remain simultaneously available during Carter failure.
2. The complete media stack must run continuously while VM 100 remains at 8–10 GiB.
3. The staged 16 GB profile breaches the 3 GiB available-memory guardrail or produces OOM/pressure.
4. Reducing VM 100 enough to fit causes unacceptable AI/automation performance or sustained guest
   swap activity.
5. Operationally managing service tiers becomes more costly or error-prone than purchasing RAM.

## Acceptance checklist and implementation state

1. **Open:** confirm `pvesr status` on Carter shows both `118-0` and `200-0` enabled, current,
   `FailCount 0`, and `State OK`. VM 200 meets this condition; final VM 118 confirmation remains.
2. **Closed 2026-07-22:** VM 199 was confirmed stopped, without a NIC or snapshots. The operator
   authorized its destruction; its configuration and owned ZFS volumes are now absent.
3. **Open:** confirm direct operator administrative access to Apophis without VM 100.
4. **Ongoing:** collect at least several representative management and HA peak-memory periods before proposing
   permanent guest reductions.
5. **Accepted 2026-07-22:** the operator accepts losing VM 100 temporarily during a Carter failure.
6. **Closed 2026-07-22:** ADR-009, `PLAN.md`, the power/autostart section, and manual-failover
   runbook were revised for the asymmetric-capacity model.

## Recommendation

Adopt a **time-bounded 16 GB trial** and make no immediate RAM purchase. Keep the incident placement,
leave media autostart disabled, verify replication, and gather representative peaks. The trial is a
success if core normal operation remains stable and the operator accepts the asymmetric Carter-loss
procedure. It fails—and 32 GB becomes the simplest correct answer—if continuous simultaneous
management and critical-VM failover is required or the measured guardrails cannot be maintained.
