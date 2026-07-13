# ADR-015: Patching & updates — auto security patches on guests, monthly rolling window on hosts

**Date:** 2026-06-17
**Status:** Accepted and implemented. Guest track live 2026-06-17; host playbook live 2026-06-19; maintenance-intent monitoring added 2026-07-13.

## Context

Patching is **manual/ad-hoc today** — there is no schedule, and the dashboard already shows
oneill carrying a backlog of pending `apt` updates (apophis ~1). As the lab grows to a 3-node
cluster (Phase 4), "remember to update everything by hand" doesn't scale and leaves a real
security-patch gap on the Debian/Ubuntu guests.

Constraints that shape the approach:

- **Two classes of machine.** *Guests* — the Debian LXCs (Tailscale, Technitium, PBS, HA-backup
  share, Monitoring, Glance) and the Ubuntu **mgmt-vm** — take normal `apt` patches and rarely
  need reboots (unprivileged LXCs share the host kernel). *Hosts* — the Proxmox nodes (apophis,
  oneill, future ThinkCentre) — need `apt dist-upgrade` and occasional **reboots** (kernel/PVE),
  which take their guests down.
- **HAOS is special.** The Home Assistant VM runs Home Assistant OS, an appliance that manages its
  own OS/Core updates through the HA UI — it is **not** an `apt` target.
- **Reboot cost changes at Phase 4.** Pre-cluster, rebooting a host = downtime for its guests.
  Post-cluster, **HA failover + live migration** cover the reboot, enabling true rolling updates.
- **Visibility is intent-aware.** A node_exporter textfile collector on every PVE host compares the
  running kernel with the newest installed `-pve` kernel (PVE often lacks
  `/var/run/reboot-required`), counts pending/security packages, and audits every running LXC for
  active unattended-upgrades enrollment. The same collector runs on the manually patched Ubuntu
  VMs. Glance surfaces the combined state (ADR-014).
- Fresh PVE nodes ship the **enterprise** apt repos, which `401` without a subscription and break
  `apt`; they must be switched to `pve-no-subscription` (done manually on oneill 2026-06-16).

## Decision

A two-track policy, both tracks owned by Ansible so they're reproducible:

### 1. Guests — automatic **security** patches (unattended)
- Install + configure **`unattended-upgrades`** on the **Debian service LXCs** (Tailscale,
  Technitium, PBS, HA-backup share, Monitoring, Glance) via a new `provision-patching.yml` (a
  play/role applied to the guest inventory group).
- **Security pocket only** (`${distro_id}:${distro_codename}-security`). Deliberately *not*
  all-updates, even for the "disposable" rebuildable LXCs — the risk of an unattended upgrade
  breaking a service outweighs the small gain, and "rebuildable" ≠ non-disruptive (e.g. Technitium
  breaking = a whole-house DNS outage). **Non-security** updates are visible in Glance and applied
  **deliberately in the monthly window**, not automatically.
- **Run at ~midday, not the ~06:00 default.** Override the `apt-daily-upgrade.timer` `OnCalendar`
  to **12:00** (local/AEST) so even automated guest patches land while the operator is around to
  notice fallout — rather than breaking overnight and surfacing as failed morning automations.
- **No automatic reboot** (`Unattended-Upgrade::Automatic-Reboot "false"`), and the guest LXCs
  **share the host kernel** (no `linux-image` inside) — so kernel security fixes are applied by
  rebooting the *host* in the monthly window, not the containers. Guests effectively never need a
  manual reboot.
- **Auto-restart services with `needrestart` (mode `a`)** so a patched library actually takes effect
  immediately (the running process otherwise keeps the old in-memory lib until it restarts) — at
  midday, no manual step. Trade-off: a brief restart blip for the affected service (seconds).
- **Notify on failure** (ntfy via the existing channel / `mail-to-root`), so a silent failure
  surfaces.
- **mgmt-vm excluded → patched manually** (for now): it's the Ansible/Claude control node, so an
  unattended upgrade breaking it mid-session is more disruptive than a service LXC. Patch it by hand
  during the host window (treated like a host). Revisit auto-patching it once the cluster makes it
  less of a single point of control.
- **HAOS excluded** — update Home Assistant OS + Core from the HA UI on the operator's cadence, with
  the native partial backup (ADR-012) as the safety net before each upgrade.

### 2. Hosts — deliberate **monthly rolling** window (manual trigger)
- **Window: the last day of each month, 12:00 (midday, AEST)** — chosen so the operator is present
  to catch any breakage, rather than patching/rebooting overnight and discovering dead automations
  the next morning. The Proxmox hosts **and the mgmt-vm** are patched in this window. **Not**
  unattended — host/PVE upgrades and reboots are done knowingly. (Manual cadence for now; a monthly
  ntfy reminder could nudge it later.)
- **Pre-cluster (now):** update one node at a time; accept brief, scheduled downtime for that node's
  guests (move the HA VM off apophis first where practical). apophis and oneill on alternating weeks
  so both aren't down together.
- **Post-cluster (Phase 4):** **rolling** — migrate/HA-failover guests off the node → `apt update &&
  apt dist-upgrade` → reboot if `node_reboot_required` → next node. HA failover covers the HA VM, so
  the window becomes effectively zero-downtime.
- **Host-prep play** (part of `provision-patching.yml` or a small `host-prep.yml`): switch
  enterprise → `pve-no-subscription` repos and disable the enterprise/ceph `.sources`, so a fresh
  node is patch-ready reproducibly (codifies the manual oneill step).

### 3. Drive it from the dashboard + alerts
- The monthly window is informed by Glance's *Package Updates* / *Reboot required* panes (hosts).
- Later (optional): an Alertmanager rule on `node_reboot_required == 1` persisting > N days, or
  growing `apt_upgrades_pending`, to nudge the window. Not required for v1.

## Consequences

- Closes the guest security-patch gap with near-zero ongoing toil; hosts stay under deliberate
  control where the risk (reboots, PVE upgrades) actually lives.
- `unattended-upgrades` can occasionally pull a bad security package. Mitigations: security-pocket
  only, failure notifications, and existing backups (PBS for mgmt-vm, Ansible-rebuild for the LXCs)
  for rollback. Per-guest config is reproducible from the playbook.
- Pre-cluster, host updates still cause brief scheduled downtime (no failover yet) — acceptable and
  predictable; the zero-downtime rolling story lands with the Phase 4 cluster, which this ADR is
  written to slot into.
- **New work, each gated when built** (`/security-review`, and infra-designer for the host-repo
  change): `provision-patching.yml` (guests `unattended-upgrades` + host-prep repos), a `runbooks.md`
  section for the monthly window + rollback, and optionally the reboot/updates Alertmanager rule.
- Resolved (operator, 2026-06-17): **window = last day of month, 12:00 AEST** (be present for
  fallout, not overnight); **mgmt-vm = manual** for now (control node); **security-only** on guests
  (no all-updates, even for disposable LXCs). Guest auto-patch timer pinned to **midday** for the
  same be-present reasoning. Revisit mgmt-vm auto-patching once clustered.

## Implementation note (2026-06-17)

**Guest track — done.** `provision-patching.yml` configures every running guest LXC, discovered via
`pct list` on both hosts (naturally = the service LXCs 110–115; mgmt-vm + HA are qemu VMs, excluded).
Per-guest setup is `ansible/files/patching/setup-unattended.sh` (idempotent): install
`unattended-upgrades` + **`needrestart` (mode `a` → auto-restart services on outdated libs, so the
patch is effective without a manual restart/reboot)**, enable the periodic timers, assert
`Automatic-Reboot "false"`, pin the `apt-daily-upgrade.timer` to **12:00 in the operator's timezone**
(`patching_timezone` group_var → calendar TZ suffix, systemd ≥ 252; DST-safe — the CTs run UTC so a
bare `12:00` would be 22:00 local), and install an ntfy **OnFailure** hook. Verified across both hosts: timer next-elapse = local noon;
`unattended-upgrade --dry-run` runs clean with allowed origins = **Debian-Security + the base
point-release pocket, not `-updates`** (Debian's recommended default — we don't widen it, so it's
security/point-release only, never the regular feature/bugfix pocket).

**Prerequisite fixed:** the PBS guest (CT 112) shipped the `pbs-enterprise` apt repo, which 401s
without a subscription and broke `apt-get update` (and would have caused daily false ntfy failures).
`provision-pbs.yml` now disables it (idempotently) in favour of the existing `pbs-no-subscription`.

**Host track — done, still deliberately manual.** `provision-host-base.yml` codifies the
`pve-no-subscription` repositories and `update-pve-host.yml` upgrades exactly one node, reports the
running-vs-installed kernel result, and never reboots unless `-e do_reboot=true` is explicitly
passed. `maintenance-collector.sh` publishes that same kernel comparison so Glance cannot falsely
show “reboot required: no” after a PVE kernel upgrade. `provision-maintenance-monitoring.yml` adds
daily update/reboot metrics for the manual Ubuntu VMs and LXC enrollment checks; alerts apply only
after defined grace periods. The operator window remains the last day of the month at 12:00 local.
